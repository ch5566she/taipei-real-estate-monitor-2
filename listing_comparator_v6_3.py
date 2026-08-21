# -*- coding: utf-8 -*-
"""
台北市士林區 / 北投區
V6.3 智慧比較樣本引擎

第46階段

設計目標：
1. 不修改既有 V6.2 comparator
2. 建立獨立 V6.3 比較引擎
3. 採分層比較樣本搜尋
4. 對比較樣本進行品質評分
5. 優先使用高品質樣本
6. 高品質樣本不足時，自動放寬搜尋條件
7. 保留「樣本不足」機制，不強行估價

比較層級：

Level 1
同社區 / 同大樓

Level 2
同路段

Level 3
同行政區 + 相近坪數 + 相近建物類型

Level 4
同行政區 + 相近坪數

Level 5
同行政區

最後：
樣本不足
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

TRANSACTIONS_FILE = DATA_DIR / "591_transactions.csv"
LISTINGS_FILE = DATA_DIR / "incoming_listings.csv"

OUTPUT_FILE = DATA_DIR / "listing_comparison_v6_3.json"


# 最低樣本門檻
MIN_SAMPLES = 3

# 最多使用比較樣本
MAX_SAMPLES = 10


# ============================================================
# 工具函式
# ============================================================

def safe_float(value: Any) -> float | None:
    """安全轉換數字。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(",", "")
    text = text.replace("萬", "")
    text = text.replace("元", "")

    try:
        return float(text)
    except ValueError:
        return None


def normalize_text(value: Any) -> str:
    """標準化文字。"""

    if value is None:
        return ""

    return re.sub(r"\s+", "", str(value).strip())


def extract_number(text: str) -> float | None:
    """從文字中抓第一個數字。"""

    if not text:
        return None

    match = re.search(r"\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def normalize_road(location: str) -> str:
    """
    標準化路段名稱。

    例如：
    德行西路88號
    德行西路 88 號

    → 德行西路
    """

    text = normalize_text(location)

    if not text:
        return ""

    # 去除門牌號碼
    text = re.sub(r"\d+(?:-\d+)*號.*$", "", text)

    # 去除樓層
    text = re.sub(r"[Bb]\d+[F樓].*$", "", text)
    text = re.sub(r"\d+[F樓].*$", "", text)

    return text


def normalize_building_type(value: Any) -> str:
    """標準化建物類型。"""

    text = normalize_text(value)

    if not text:
        return ""

    mapping = {
        "電梯大樓": "電梯大樓",
        "華廈": "華廈",
        "公寓": "公寓",
        "透天": "透天",
        "透天厝": "透天",
        "大樓": "電梯大樓",
    }

    for key, result in mapping.items():
        if key in text:
            return result

    return text


def extract_floor(value: Any) -> float | None:
    """取得樓層數字。"""

    return extract_number(normalize_text(value))


# ============================================================
# CSV 讀取
# ============================================================

def read_csv(path: Path) -> list[dict[str, Any]]:
    """讀取 CSV。"""

    if not path.exists():
        print(f"⚠️ 找不到資料檔：{path}")
        return []

    rows: list[dict[str, Any]] = []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            rows.append(dict(row))

    return rows


# ============================================================
# 建立標準化交易資料
# ============================================================

def normalize_transaction(row: dict[str, Any]) -> dict[str, Any]:
    """將交易資料轉成比較引擎使用格式。"""

    location = normalize_text(
        row.get("location")
        or row.get("address")
        or row.get("路段")
        or ""
    )

    district = normalize_text(
        row.get("district")
        or row.get("行政區")
        or ""
    )

    building_type = normalize_building_type(
        row.get("building_type")
        or row.get("建物型態")
        or ""
    )

    area = safe_float(
        row.get("building_area")
        or row.get("area")
        or row.get("建物面積")
        or row.get("坪數")
    )

    unit_price = safe_float(
        row.get("unit_price")
        or row.get("單價")
        or row.get("price_per_ping")
    )

    floor = extract_floor(
        row.get("floor")
        or row.get("樓層")
        or ""
    )

    return {
        "raw": row,
        "district": district,
        "location": location,
        "road": normalize_road(location),
        "building_type": building_type,
        "area": area,
        "unit_price": unit_price,
        "floor": floor,
    }


# ============================================================
# 標準化在售物件
# ============================================================

def normalize_listing(row: dict[str, Any]) -> dict[str, Any]:
    """將在售物件轉成比較引擎格式。"""

    location = normalize_text(
        row.get("location")
        or row.get("address")
        or ""
    )

    district = normalize_text(
        row.get("district")
        or ""
    )

    building_type = normalize_building_type(
        row.get("building_type")
        or ""
    )

    area = safe_float(
        row.get("building_area")
        or row.get("area")
        or ""
    )

    unit_price = safe_float(
        row.get("unit_price")
        or ""
    )

    floor = extract_floor(
        row.get("floor")
        or ""
    )

    return {
        "raw": row,
        "listing_id": row.get("listing_id", ""),
        "title": row.get("title", ""),
        "district": district,
        "location": location,
        "road": normalize_road(location),
        "building_type": building_type,
        "area": area,
        "unit_price": unit_price,
        "floor": floor,
    }


# ============================================================
# 坪數相似度
# ============================================================

def area_score(target: float | None, sample: float | None) -> float:
    """
    坪數相似度。

    越接近 100 越好。
    """

    if target is None or sample is None:
        return 0.0

    if target <= 0:
        return 0.0

    diff_ratio = abs(sample - target) / target

    if diff_ratio <= 0.05:
        return 100.0

    if diff_ratio <= 0.10:
        return 80.0

    if diff_ratio <= 0.15:
        return 60.0

    if diff_ratio <= 0.25:
        return 35.0

    return 10.0


# ============================================================
# 樓層相似度
# ============================================================

def floor_score(target: float | None, sample: float | None) -> float:
    """樓層相似度。"""

    if target is None or sample is None:
        return 0.0

    diff = abs(target - sample)

    if diff == 0:
        return 100.0

    if diff <= 2:
        return 80.0

    if diff <= 4:
        return 60.0

    if diff <= 7:
        return 35.0

    return 10.0


# ============================================================
# 樣本品質評分
# ============================================================

def calculate_quality(
    target: dict[str, Any],
    sample: dict[str, Any],
) -> tuple[int, list[str]]:
    """
    計算比較樣本品質。

    分數越高代表越適合拿來估價。
    """

    score = 0
    reasons: list[str] = []

    # --------------------------------------------------------
    # 行政區
    # --------------------------------------------------------

    if (
        target["district"]
        and sample["district"]
        and target["district"] == sample["district"]
    ):
        score += 20
        reasons.append("同行政區")

    # --------------------------------------------------------
    # 路段
    # --------------------------------------------------------

    if (
        target["road"]
        and sample["road"]
        and target["road"] == sample["road"]
    ):
        score += 25
        reasons.append("同路段")

    # --------------------------------------------------------
    # 建物類型
    # --------------------------------------------------------

    if (
        target["building_type"]
        and sample["building_type"]
        and target["building_type"] == sample["building_type"]
    ):
        score += 20
        reasons.append("同建物類型")

    # --------------------------------------------------------
    # 坪數
    # --------------------------------------------------------

    a_score = area_score(
        target["area"],
        sample["area"]
    )

    if a_score >= 80:
        score += 20
        reasons.append("坪數高度接近")
    elif a_score >= 60:
        score += 12
        reasons.append("坪數接近")
    elif a_score >= 35:
        score += 5
        reasons.append("坪數部分接近")

    # --------------------------------------------------------
    # 樓層
    # --------------------------------------------------------

    f_score = floor_score(
        target["floor"],
        sample["floor"]
    )

    if f_score >= 80:
        score += 10
        reasons.append("樓層接近")
    elif f_score >= 60:
        score += 6
        reasons.append("樓層部分接近")

    # --------------------------------------------------------
    # 樣本單價存在
    # --------------------------------------------------------

    if sample["unit_price"] is not None:
        score += 5
        reasons.append("具有效單價")

    return score, reasons


# ============================================================
# 判斷比較層級
# ============================================================

def determine_level(
    target: dict[str, Any],
    sample: dict[str, Any],
) -> int:

    same_district = (
        target["district"]
        and sample["district"]
        and target["district"] == sample["district"]
    )

    same_road = (
        target["road"]
        and sample["road"]
        and target["road"] == sample["road"]
    )

    same_building = (
        target["building_type"]
        and sample["building_type"]
        and target["building_type"] == sample["building_type"]
    )

    a_score = area_score(
        target["area"],
        sample["area"]
    )

    if same_district and same_road and same_building and a_score >= 80:
        return 1

    if same_district and same_road:
        return 2

    if same_district and a_score >= 60 and same_building:
        return 3

    if same_district and a_score >= 60:
        return 4

    if same_district:
        return 5

    return 6


# ============================================================
# 比較樣本搜尋
# ============================================================

def find_comparables(
    target: dict[str, Any],
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    candidates: list[dict[str, Any]] = []

    for sample in transactions:

        # 沒有單價的資料不能作為正式比較樣本
        if sample["unit_price"] is None:
            continue

        # 完全不同行政區暫不採用
        if (
            target["district"]
            and sample["district"]
            and target["district"] != sample["district"]
        ):
            continue

        score, reasons = calculate_quality(
            target,
            sample
        )

        level = determine_level(
            target,
            sample
        )

        candidate = {
            **sample,
            "quality_score": score,
            "quality_reasons": reasons,
            "comparison_level": level,
        }

        candidates.append(candidate)

    # 先比較層級，再品質分數
    candidates.sort(
        key=lambda item: (
            item["comparison_level"],
            -item["quality_score"],
        )
    )

    return candidates[:MAX_SAMPLES]


# ============================================================
# 統計比較結果
# ============================================================

def calculate_market_stats(
    samples: list[dict[str, Any]]
) -> dict[str, Any]:

    prices = [
        sample["unit_price"]
        for sample in samples
        if sample["unit_price"] is not None
    ]

    if not prices:
        return {
            "count": 0,
            "average": None,
            "median": None,
            "q1": None,
            "q3": None,
        }

    prices = sorted(prices)

    count = len(prices)

    average = sum(prices) / count

    median = (
        prices[count // 2]
        if count % 2 == 1
        else (
            prices[count // 2 - 1]
            + prices[count // 2]
        ) / 2
    )

    q1_index = max(0, math.floor((count - 1) * 0.25))
    q3_index = min(count - 1, math.floor((count - 1) * 0.75))

    return {
        "count": count,
        "average": round(average, 2),
        "median": round(median, 2),
        "q1": round(prices[q1_index], 2),
        "q3": round(prices[q3_index], 2),
    }


# ============================================================
# 信心判斷
# ============================================================

def confidence_level(
    samples: list[dict[str, Any]]
) -> str:

    count = len(samples)

    level1 = sum(
        1
        for sample in samples
        if sample["comparison_level"] == 1
    )

    level2 = sum(
        1
        for sample in samples
        if sample["comparison_level"] == 2
    )

    if level1 >= 3:
        return "高"

    if count >= 5 and level2 >= 2:
        return "中高"

    if count >= 3:
        return "中"

    return "低"


# ============================================================
# 單一物件分析
# ============================================================

def analyze_listing(
    listing: dict[str, Any],
    transactions: list[dict[str, Any]],
) -> dict[str, Any]:

    samples = find_comparables(
        listing,
        transactions
    )

    stats = calculate_market_stats(samples)

    confidence = confidence_level(samples)

    if len(samples) < MIN_SAMPLES:
        status = "樣本不足"
    else:
        status = "可進行市場比較"

    return {
        "listing_id": listing["listing_id"],
        "title": listing["title"],
        "district": listing["district"],
        "location": listing["location"],
        "target_area": listing["area"],
        "target_unit_price": listing["unit_price"],
        "status": status,
        "confidence": confidence,
        "sample_count": len(samples),
        "market_stats": stats,
        "comparables": [
            {
                "comparison_level": sample["comparison_level"],
                "quality_score": sample["quality_score"],
                "quality_reasons": sample["quality_reasons"],
                "district": sample["district"],
                "location": sample["location"],
                "area": sample["area"],
                "unit_price": sample["unit_price"],
                "floor": sample["floor"],
                "building_type": sample["building_type"],
                "raw": sample["raw"],
            }
            for sample in samples
        ],
    }


# ============================================================
# 主程式
# ============================================================

def main() -> None:

    print("=" * 60)
    print("第46階段：V6.3 智慧比較樣本引擎")
    print("=" * 60)

    print()
    print("讀取實價交易資料...")
    
    transaction_rows = read_csv(
        TRANSACTIONS_FILE
    )

    print(
        f"實價原始資料：{len(transaction_rows)} 筆"
    )

    transactions = [
        normalize_transaction(row)
        for row in transaction_rows
    ]

    print(
        f"有效比較資料：{len(transactions)} 筆"
    )

    print()
    print("讀取在售物件...")

    listing_rows = read_csv(
        LISTINGS_FILE
    )

    print(
        f"在售物件：{len(listing_rows)} 筆"
    )

    listings = [
        normalize_listing(row)
        for row in listing_rows
    ]

    print()
    print("開始 V6.3 智慧比較...")
    print()

    results = []

    for listing in listings:

        result = analyze_listing(
            listing,
            transactions
        )

        results.append(result)

        print("-" * 60)

        print(
            f"物件：{result['listing_id']}"
        )

        print(
            f"標題：{result['title']}"
        )

        print(
            f"行政區：{result['district']}"
        )

        print(
            f"位置：{result['location']}"
        )

        print(
            f"比較狀態：{result['status']}"
        )

        print(
            f"信心度：{result['confidence']}"
        )

        print(
            f"比較樣本：{result['sample_count']} 筆"
        )

        stats = result["market_stats"]

        print(
            f"市場平均：{stats['average']}"
        )

        print(
            f"市場中位數：{stats['median']}"
        )

        for index, sample in enumerate(
            result["comparables"],
            start=1
        ):

            print(
                f"  #{index} "
                f"Level {sample['comparison_level']} "
                f"| 品質 {sample['quality_score']} "
                f"| {sample['unit_price']} 萬/坪"
            )

    # --------------------------------------------------------
    # 輸出 JSON
    # --------------------------------------------------------

    output = {
        "version": "V6.3",
        "stage": "第46階段",
        "generated_at": datetime.now().isoformat(
            timespec="seconds"
        ),
        "settings": {
            "min_samples": MIN_SAMPLES,
            "max_samples": MAX_SAMPLES,
            "comparison_levels": [
                "同社區/同大樓",
                "同路段",
                "同行政區+相近坪數+相近建物類型",
                "同行政區+相近坪數",
                "同行政區",
            ],
        },
        "summary": {
            "listing_count": len(results),
            "sample_sufficient": sum(
                1
                for result in results
                if result["sample_count"] >= MIN_SAMPLES
            ),
            "sample_insufficient": sum(
                1
                for result in results
                if result["sample_count"] < MIN_SAMPLES
            ),
        },
        "results": results,
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 60)
    print("V6.3 比較引擎完成")
    print("=" * 60)

    print(
        f"輸出：{OUTPUT_FILE}"
    )

    print(
        f"分析物件：{len(results)} 筆"
    )

    print(
        "目前 V6.2 未被修改。"
    )


if __name__ == "__main__":
    main()
