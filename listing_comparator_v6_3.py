# -*- coding: utf-8 -*-

"""
台北市士林區 / 北投區
V6.3 智慧比較樣本分析層

設計原則：

V6.2：
    負責真正的比較樣本選擇與價格計算

V6.3：
    不重新估價
    不修改 V6.2
    只負責：

    1. A/B/C/D/E/F 樣本診斷
    2. 核心樣本充足度
    3. 市場單價分析
    4. 開價偏離分析
    5. 價格定位
    6. 信心度
    7. 房仲文字判讀
    8. JSON / CSV 輸出

資料來源：
    data/pricing_decisions.csv
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================
# 路徑
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INPUT_FILE = DATA_DIR / "pricing_decisions.csv"

OUTPUT_JSON = DATA_DIR / "comparison_analysis_v6_3.json"
OUTPUT_CSV = DATA_DIR / "comparison_analysis_v6_3.csv"


# ============================================================
# 基本設定
# ============================================================

MIN_CORE_SAMPLES = 3

# 開價偏離門檻
HIGH_PRICE_THRESHOLD = 0.10
VERY_HIGH_PRICE_THRESHOLD = 0.20

LOW_PRICE_THRESHOLD = -0.10
VERY_LOW_PRICE_THRESHOLD = -0.20


# ============================================================
# 基本工具
# ============================================================

def safe_float(value: Any) -> float | None:

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = (
        text
        .replace(",", "")
        .replace("%", "")
        .replace("萬", "")
        .replace("元", "")
    )

    try:
        return float(text)
    except ValueError:
        return None


def safe_int(value: Any) -> int:

    number = safe_float(value)

    if number is None:
        return 0

    return int(number)


def read_csv(path: Path) -> list[dict[str, Any]]:

    if not path.exists():
        print(f"❌ 找不到資料檔：{path}")
        return []

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        return [
            dict(row)
            for row in reader
        ]


# ============================================================
# 樣本統計
# ============================================================

def sample_statistics(row: dict[str, Any]) -> dict[str, Any]:

    a = safe_int(row.get("grade_a_count"))
    b = safe_int(row.get("grade_b_count"))
    c = safe_int(row.get("grade_c_count"))
    d = safe_int(row.get("grade_d_count"))
    e = safe_int(row.get("grade_e_count"))

    extension = safe_int(
        row.get("extension_comparable_count")
    )

    comparable = safe_int(
        row.get("comparable_count")
    )

    core = safe_int(
        row.get("core_comparable_count")
    )

    excluded = safe_int(
        row.get("excluded_count")
    )

    # --------------------------------------------------------
    # 核心樣本
    # --------------------------------------------------------

    core_abc = a + b + c

    # --------------------------------------------------------
    # A/B 高品質核心
    # --------------------------------------------------------

    core_ab = a + b

    # --------------------------------------------------------
    # 計算比例
    # --------------------------------------------------------

    if comparable > 0:
        core_ratio = core_abc / comparable
    else:
        core_ratio = 0.0

    if comparable > 0:
        ab_ratio = core_ab / comparable
    else:
        ab_ratio = 0.0

    return {
        "grade_a_count": a,
        "grade_b_count": b,
        "grade_c_count": c,
        "grade_d_count": d,
        "grade_e_count": e,
        "extension_comparable_count": extension,
        "comparable_count": comparable,
        "core_comparable_count": core,
        "core_ab_count": core_ab,
        "core_abc_count": core_abc,
        "excluded_count": excluded,
        "core_ratio": round(
            core_ratio * 100,
            2
        ),
        "ab_ratio": round(
            ab_ratio * 100,
            2
        ),
    }


# ============================================================
# 樣本品質
# ============================================================

def evaluate_sample_quality(
    stats: dict[str, Any],
    confidence: str | None,
) -> tuple[str, str]:

    core_abc = stats["core_abc_count"]
    core_ab = stats["core_ab_count"]
    comparable = stats["comparable_count"]

    # --------------------------------------------------------
    # 完全不足
    # --------------------------------------------------------

    if core_abc < MIN_CORE_SAMPLES:

        return (
            "低",
            "A/B/C 核心比較樣本不足3筆，"
            "不宜視為正式市場估價依據。"
        )

    # --------------------------------------------------------
    # 高品質
    # --------------------------------------------------------

    if (
        core_ab >= 5
        and comparable >= 5
    ):

        return (
            "高",
            "A/B 高品質比較樣本充足，"
            "且核心樣本占比良好。"
        )

    if (
        core_abc >= 5
        and comparable >= 5
    ):

        return (
            "中高",
            "A/B/C 核心比較樣本充足，"
            "可作為主要市場判讀依據。"
        )

    # --------------------------------------------------------
    # 中等
    # --------------------------------------------------------

    if core_abc >= 3:

        return (
            "中",
            "已有至少3筆A/B/C核心樣本，"
            "但樣本品質或數量仍有限。"
        )

    return (
        "低",
        "比較樣本品質不足。"
    )


# ============================================================
# 價格偏離
# ============================================================

def calculate_price_position(
    current_unit: float | None,
    market_unit: float | None,
) -> dict[str, Any]:

    if (
        current_unit is None
        or market_unit is None
        or market_unit <= 0
    ):

        return {
            "gap_percent": None,
            "position": "無法判斷",
            "severity": "未知",
        }

    gap = (
        current_unit / market_unit
    ) - 1

    gap_percent = round(
        gap * 100,
        2
    )

    # --------------------------------------------------------
    # 價格偏高
    # --------------------------------------------------------

    if gap >= VERY_HIGH_PRICE_THRESHOLD:

        return {
            "gap_percent": gap_percent,
            "position": "明顯偏高",
            "severity": "高",
        }

    if gap >= HIGH_PRICE_THRESHOLD:

        return {
            "gap_percent": gap_percent,
            "position": "偏高",
            "severity": "中高",
        }

    # --------------------------------------------------------
    # 價格偏低
    # --------------------------------------------------------

    if gap <= VERY_LOW_PRICE_THRESHOLD:

        return {
            "gap_percent": gap_percent,
            "position": "明顯偏低",
            "severity": "高",
        }

    if gap <= LOW_PRICE_THRESHOLD:

        return {
            "gap_percent": gap_percent,
            "position": "偏低",
            "severity": "中高",
        }

    # --------------------------------------------------------
    # 合理區間
    # --------------------------------------------------------

    return {
        "gap_percent": gap_percent,
        "position": "接近市場核心行情",
        "severity": "低",
    }


# ============================================================
# 市場價格區間
# ============================================================

def estimate_market_range(
    market_unit: float | None,
    confidence: str,
) -> dict[str, Any]:

    if market_unit is None:

        return {
            "low_unit": None,
            "high_unit": None,
            "range_available": False,
        }

    # --------------------------------------------------------
    # 注意：
    # 這裡不是重新估價。
    #
    # 只是建立「市場參考帶」。
    #
    # 真正正式估價仍由 V6.2 負責。
    # --------------------------------------------------------

    if confidence == "高":

        low_factor = 0.96
        high_factor = 1.04

    elif confidence == "中高":

        low_factor = 0.94
        high_factor = 1.06

    elif confidence == "中":

        low_factor = 0.92
        high_factor = 1.08

    else:

        # 樣本不足時不輸出正式區間
        return {
            "low_unit": None,
            "high_unit": None,
            "range_available": False,
        }

    return {
        "low_unit": round(
            market_unit * low_factor,
            2
        ),
        "high_unit": round(
            market_unit * high_factor,
            2
        ),
        "range_available": True,
    }


# ============================================================
# 房仲判讀
# ============================================================

def generate_agent_comment(
    row: dict[str, Any],
    stats: dict[str, Any],
    quality: str,
    quality_reason: str,
    price_position: dict[str, Any],
) -> str:

    comparable = stats["comparable_count"]
    core = stats["core_abc_count"]

    position = price_position["position"]

    # --------------------------------------------------------
    # 樣本不足
    # --------------------------------------------------------

    if core < MIN_CORE_SAMPLES:

        return (
            "目前核心比較樣本不足，"
            "不建議直接將單一成交案例視為市場平均。"
            "目前價格僅可作為初步市場參考，"
            "建議補充更多同路段、相近坪數及相近建物型態的成交資料。"
        )

    # --------------------------------------------------------
    # 明顯偏高
    # --------------------------------------------------------

    if position == "明顯偏高":

        return (
            f"目前開價明顯高於核心市場參考值。"
            f"本次共有{comparable}筆比較樣本，"
            f"其中A/B/C核心樣本{core}筆。"
            "若屋況、樓層、景觀、裝潢或特殊條件沒有明顯優勢，"
            "買方議價空間通常較大。"
        )

    # --------------------------------------------------------
    # 偏高
    # --------------------------------------------------------

    if position == "偏高":

        return (
            "目前開價高於核心市場行情，"
            "但仍可能透過屋況、樓層、採光、景觀、裝潢及車位等條件進行合理修正。"
            "建議買方先以核心成交行情作為議價基準。"
        )

    # --------------------------------------------------------
    # 偏低
    # --------------------------------------------------------

    if position == "明顯偏低":

        return (
            "目前開價明顯低於核心市場參考值。"
            "建議進一步確認屋況、產權、樓層、採光、嫌惡設施、"
            "車位及其他特殊交易因素，避免僅依單價判斷。"
        )

    # --------------------------------------------------------
    # 接近市場
    # --------------------------------------------------------

    return (
        "目前開價與核心市場行情接近。"
        "若物件屋況、樓層、採光、景觀、裝潢及車位條件正常，"
        "價格具有一定市場合理性。"
    )


# ============================================================
# 單筆分析
# ============================================================

def analyze_row(
    row: dict[str, Any]
) -> dict[str, Any]:

    stats = sample_statistics(row)

    confidence_input = (
        row.get("confidence")
        or ""
    )

    quality, quality_reason = evaluate_sample_quality(
        stats,
        confidence_input,
    )

    current_unit = safe_float(
        row.get("current_unit_price")
    )

    market_unit = safe_float(
        row.get("weighted_market_unit_price")
    )

    # 若沒有加權市場單價
    # 使用成交中位單價作為參考
    if market_unit is None:

        market_unit = safe_float(
            row.get(
                "median_transaction_unit_price"
            )
        )

    price_position = calculate_price_position(
        current_unit,
        market_unit,
    )

    market_range = estimate_market_range(
        market_unit,
        quality,
    )

    agent_comment = generate_agent_comment(
        row,
        stats,
        quality,
        quality_reason,
        price_position,
    )

    return {

        "listing_id":
            row.get("listing_id", ""),

        "district":
            row.get("district", ""),

        "location":
            row.get("location", ""),

        "title":
            row.get("title", ""),

        "current_price":
            safe_float(
                row.get("current_price")
            ),

        "current_unit_price":
            current_unit,

        "market_reference_unit_price":
            market_unit,

        "median_transaction_unit_price":
            safe_float(
                row.get(
                    "median_transaction_unit_price"
                )
            ),

        "weighted_market_unit_price":
            safe_float(
                row.get(
                    "weighted_market_unit_price"
                )
            ),

        # ----------------------------------------------------
        # 樣本
        # ----------------------------------------------------

        "comparable_count":
            stats["comparable_count"],

        "core_comparable_count":
            stats["core_comparable_count"],

        "core_ab_count":
            stats["core_ab_count"],

        "core_abc_count":
            stats["core_abc_count"],

        "grade_a_count":
            stats["grade_a_count"],

        "grade_b_count":
            stats["grade_b_count"],

        "grade_c_count":
            stats["grade_c_count"],

        "grade_d_count":
            stats["grade_d_count"],

        "grade_e_count":
            stats["grade_e_count"],

        "extension_comparable_count":
            stats["extension_comparable_count"],

        "excluded_count":
            stats["excluded_count"],

        "core_sample_ratio":
            stats["core_ratio"],

        # ----------------------------------------------------
        # 品質
        # ----------------------------------------------------

        "v62_price_grade":
            row.get("price_grade", ""),

        "v62_confidence":
            confidence_input,

        "v63_quality":
            quality,

        "v63_quality_reason":
            quality_reason,

        # ----------------------------------------------------
        # 價格偏離
        # ----------------------------------------------------

        "price_gap_percent":
            price_position["gap_percent"],

        "price_position":
            price_position["position"],

        "price_severity":
            price_position["severity"],

        # ----------------------------------------------------
        # 市場參考區間
        # ----------------------------------------------------

        "market_range_available":
            market_range["range_available"],

        "market_low_unit_price":
            market_range["low_unit"],

        "market_high_unit_price":
            market_range["high_unit"],

        # ----------------------------------------------------
        # 房仲判讀
        # ----------------------------------------------------

        "agent_comment":
            agent_comment,

        "generated_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),
    }


# ============================================================
# CSV 輸出
# ============================================================

def write_csv(
    rows: list[dict[str, Any]]
) -> None:

    if not rows:
        return

    fieldnames = list(
        rows[0].keys()
    )

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(rows)


# ============================================================
# JSON 輸出
# ============================================================

def write_json(
    rows: list[dict[str, Any]]
) -> None:

    output = {

        "version": "V6.3",

        "stage":
            "第46-4階段",

        "generated_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "purpose":
            "V6.2價格決策結果之智慧分析與房仲判讀",

        "important_rule":
            "V6.3不重新計算V6.2正式估價",

        "results":
            rows,

    }

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# 主程式
# ============================================================

def main() -> None:

    print("=" * 70)
    print("V6.3 智慧比較樣本分析層")
    print("=" * 70)

    print()
    print(
        f"讀取：{INPUT_FILE}"
    )

    rows = read_csv(
        INPUT_FILE
    )

    if not rows:

        print(
            "❌ 沒有讀到 pricing_decisions.csv"
        )

        return

    print(
        f"讀取房源：{len(rows)} 筆"
    )

    print()

    results = []

    for row in rows:

        result = analyze_row(
            row
        )

        results.append(
            result
        )

        print("-" * 70)

        print(
            f"物件：{result['listing_id']}"
        )

        print(
            f"位置：{result['location']}"
        )

        print(
            f"目前開價："
            f"{result['current_unit_price']} 萬/坪"
        )

        print(
            f"市場參考："
            f"{result['market_reference_unit_price']} 萬/坪"
        )

        print(
            f"比較樣本："
            f"{result['comparable_count']} 筆"
        )

        print(
            f"A/B/C核心樣本："
            f"{result['core_abc_count']} 筆"
        )

        print(
            f"樣本品質："
            f"{result['v63_quality']}"
        )

        print(
            f"V6.2信心："
            f"{result['v62_confidence']}"
        )

        print(
            f"價格偏離："
            f"{result['price_gap_percent']}%"
        )

        print(
            f"市場定位："
            f"{result['price_position']}"
        )

        print(
            f"房仲判讀："
            f"{result['agent_comment']}"
        )

    write_csv(
        results
    )

    write_json(
        results
    )

    print()
    print("=" * 70)
    print("V6.3 分析完成")
    print("=" * 70)

    print(
        f"CSV：{OUTPUT_CSV}"
    )

    print(
        f"JSON：{OUTPUT_JSON}"
    )

    print()
    print(
        "注意：V6.3 沒有修改 V6.2 正式估價結果。"
    )


if __name__ == "__main__":
    main()
