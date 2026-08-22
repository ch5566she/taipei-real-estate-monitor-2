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
CURRENT_LISTINGS_FILE = DATA_DIR / "current_listings.csv"

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
# 第51階段：房源資料品質 A-F
# ============================================================

QUALITY_CORE_FIELDS = [
    "listing_id",
    "total_price",
    "building_area",
    "current_unit_price",
]

QUALITY_SUPPLEMENT_FIELDS = [
    "location",
    "floor",
    "total_floors",
    "rooms",
    "age",
    "building_type",
    "url",
]

def first_value(row: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return value
    return None


def normalize_listing_id(value: Any) -> str:
    return str(value or "").strip()


def evaluate_listing_data_quality(
    listing: dict[str, Any],
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    第51階段資料品質分級。

    注意：
    - 這是「房源資料完整度」分級，不是 V6.2 的成交樣本品質。
    - 不重新估價、不補造缺失資料。
    - V6.2 的 formal_valuation_eligible 原值直接保留。
    """
    pricing = pricing or {}

    merged = dict(listing)
    for key, value in pricing.items():
        if value not in (None, ""):
            merged[key] = value

    listing_id = normalize_listing_id(
        first_value(merged, ["listing_id", "591_id", "物件編號"])
    )

    total_price = safe_float(
        first_value(merged, ["total_price", "current_price", "price", "總價", "售價"])
    )

    building_area = safe_float(
        first_value(merged, ["building_area", "area", "坪數", "建物坪數", "建坪"])
    )

    current_unit = safe_float(
        first_value(merged, ["current_unit_price", "unit_price", "單價", "每坪單價"])
    )

    missing_core = []

    if not listing_id:
        missing_core.append("listing_id")
    if total_price is None:
        missing_core.append("total_price")
    if building_area is None:
        missing_core.append("building_area")
    if current_unit is None:
        missing_core.append("current_unit_price")

    missing_supplement = []

    alias_map = {
        "location": ["location", "address", "addr", "地址", "路段"],
        "floor": ["floor", "樓層"],
        "total_floors": ["total_floors", "total_floor", "總樓層"],
        "rooms": ["rooms", "房數", "房"],
        "age": ["age", "屋齡"],
        "building_type": ["building_type", "建物型態", "建物類型"],
        "url": ["url", "591_url", "網址"],
    }

    for field, aliases in alias_map.items():
        if not clean_value(first_value(merged, aliases)):
            missing_supplement.append(field)

    supplement_complete = len(QUALITY_SUPPLEMENT_FIELDS) - len(missing_supplement)
    core_complete = len(missing_core) == 0

    # A-F 是「房源資料完整度」，與 V6.3 樣本品質低/中/高分開。
    if not listing_id and total_price is None:
        grade = "F"
        reason = "缺少物件編號與總價，無法建立可靠房源紀錄。"
    elif total_price is None:
        grade = "E"
        reason = "缺少總價，無法進行價格層級分析。"
    elif building_area is None:
        grade = "D"
        reason = "有總價但缺少建物坪數，無法建立可靠的每坪價格基礎。"
    elif current_unit is None:
        grade = "D"
        reason = "已有總價與坪數，但目前沒有可用單價。"
    elif supplement_complete >= 6:
        grade = "A"
        reason = "價格核心資料完整，且大部分房源結構欄位完整。"
    elif supplement_complete >= 4:
        grade = "B"
        reason = "價格核心資料完整，並有足夠補充欄位支援房仲實戰判讀。"
    else:
        grade = "C"
        reason = "價格核心資料完整，但地址、樓層、屋齡等補充欄位仍有缺漏。"

    formal = pricing.get("formal_valuation_eligible")
    if str(formal).strip().lower() in {"true", "1", "yes", "y"}:
        formal_status = "是"
    elif pricing:
        formal_status = "否"
    else:
        formal_status = "否"

    return {
        "data_quality_grade": grade,
        "data_quality_reason": reason,
        "data_quality_core_complete": core_complete,
        "data_quality_missing_core_fields": ",".join(missing_core),
        "data_quality_missing_fields": ",".join(
            missing_core + missing_supplement
        ),
        "data_quality_supplement_complete": supplement_complete,
        "data_quality_supplement_total": len(QUALITY_SUPPLEMENT_FIELDS),
        "formal_valuation_eligible": formal_status,
        "formal_valuation_reason": (
            pricing.get("formal_valuation_reason", "")
            if pricing
            else "尚未進入 V6.2 正式估價流程，或 V6.2 沒有產生此物件的決策資料。"
        ),
    }


def clean_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def empty_v63_result(listing: dict[str, Any]) -> dict[str, Any]:
    """沒有 V6.2 決策時，建立不帶價格推估的安全結果。"""
    quality = evaluate_listing_data_quality(listing, None)

    return {
        "listing_id": listing.get("listing_id", ""),
        "district": listing.get("district", ""),
        "location": listing.get("location", ""),
        "title": listing.get("title", ""),
        "current_price": safe_float(listing.get("total_price")),
        "current_unit_price": safe_float(listing.get("unit_price")),
        "market_reference_unit_price": None,
        "median_transaction_unit_price": None,
        "weighted_market_unit_price": None,
        "comparable_count": 0,
        "core_comparable_count": 0,
        "core_ab_count": 0,
        "core_abc_count": 0,
        "grade_a_count": 0,
        "grade_b_count": 0,
        "grade_c_count": 0,
        "grade_d_count": 0,
        "grade_e_count": 0,
        "extension_comparable_count": 0,
        "excluded_count": 0,
        "core_sample_ratio": 0,
        "v62_price_grade": "",
        "v62_confidence": "",
        "v63_quality": "低",
        "v63_quality_reason": "尚未取得 V6.2 比較決策資料，無法進行成交樣本判讀。",
        "price_gap_percent": None,
        "price_position": "無法判斷",
        "price_severity": "未知",
        "market_range_available": False,
        "market_low_unit_price": None,
        "market_high_unit_price": None,
        "agent_comment": (
            "目前沒有 V6.2 決策資料，因此不做市場價格推估。"
            "先補齊坪數、樓層、屋齡與位置等資料，再進行正式比價。"
        ),
        **quality,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


# ============================================================
# 單筆分析
# ============================================================

def analyze_row(
    row: dict[str, Any],
    listing_context: dict[str, Any] | None = None,
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

        # ----------------------------------------------------
        # 第51階段：房源資料品質 A-F
        # ----------------------------------------------------
        **evaluate_listing_data_quality(
            listing_context or row,
            row,
        ),

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

        "version": "V6.3.1",

        "stage":
            "第51階段｜房源資料品質 A-F 分級",

        "generated_at":
            datetime.now().isoformat(
                timespec="seconds"
            ),

        "purpose":
            "V6.2價格決策結果之智慧分析、房源資料品質 A-F 分級與房仲判讀",

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
    print("V6.3 智慧比較樣本分析層｜第51階段")
    print("=" * 70)

    print()
    print(f"V6.2決策輸入：{INPUT_FILE}")
    print(f"在售房源輸入：{CURRENT_LISTINGS_FILE}")

    pricing_rows = read_csv(INPUT_FILE)
    listing_rows = read_csv(CURRENT_LISTINGS_FILE)

    if not pricing_rows and not listing_rows:
        print("❌ pricing_decisions.csv 與 current_listings.csv 都沒有資料")
        return

    pricing_map = {
        normalize_listing_id(row.get("listing_id")): row
        for row in pricing_rows
        if normalize_listing_id(row.get("listing_id"))
    }

    # 優先以 current_listings.csv 作為「全量房源母表」，
    # 再把 V6.2 決策依 listing_id 合併進來。
    if listing_rows:
        source_rows = listing_rows
    else:
        source_rows = pricing_rows

    print(f"全量在售房源：{len(source_rows)} 筆")
    print(f"V6.2 已產生決策：{len(pricing_rows)} 筆")

    results = []

    for listing in source_rows:
        listing_id = normalize_listing_id(listing.get("listing_id"))
        pricing = pricing_map.get(listing_id)

        if pricing:
            result = analyze_row(
                pricing,
                listing_context=listing,
            )
        else:
            result = empty_v63_result(listing)

        results.append(result)

        print("-" * 70)
        print(f"物件：{result['listing_id']}")
        print(f"資料品質：{result['data_quality_grade']}級")
        print(f"缺少核心欄位：{result['data_quality_missing_core_fields'] or '無'}")
        print(f"缺少欄位：{result['data_quality_missing_fields'] or '無'}")
        print(f"正式估價：{result['formal_valuation_eligible']}")
        print(f"比較樣本：{result['comparable_count']} 筆")
        print(f"A/B/C核心樣本：{result['core_abc_count']} 筆")
        print(f"V6.3樣本品質：{result['v63_quality']}")
        print(f"市場定位：{result['price_position']}")

    # --------------------------------------------------------
    # 第51階段統計摘要
    # --------------------------------------------------------
    grade_counts = {
        grade: sum(
            1 for item in results
            if item.get("data_quality_grade") == grade
        )
        for grade in ["A", "B", "C", "D", "E", "F"]
    }

    formal_count = sum(
        1 for item in results
        if item.get("formal_valuation_eligible") == "是"
    )

    print()
    print("=" * 70)
    print("第51階段｜房源資料品質摘要")
    print("=" * 70)
    print(f"全量房源：{len(results)} 筆")
    print(
        " | ".join(
            f"{grade}級：{grade_counts[grade]} 筆"
            for grade in ["A", "B", "C", "D", "E", "F"]
        )
    )
    print(f"V6.2正式估價資格：{formal_count} 筆")
    print("=" * 70)

    write_csv(results)
    write_json(results)

    print()
    print("=" * 70)
    print("V6.3 第51階段分析完成")
    print("=" * 70)
    print(f"CSV：{OUTPUT_CSV}")
    print(f"JSON：{OUTPUT_JSON}")
    print()
    print("重要：V6.3 沒有重新計算或修改 V6.2 正式估價結果。")


if __name__ == "__main__":
    main()
