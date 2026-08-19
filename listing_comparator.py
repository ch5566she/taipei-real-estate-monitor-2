# -*- coding: utf-8 -*-
"""
台北市士林區／北投區
第20階段：在售物件 × 實價成交比價引擎

功能：
1. 讀取 data/current_listings.csv
2. 讀取 data/taipei_transactions.csv
3. 只使用住宅買賣成交資料
4. 排除純土地、租賃等非住宅成交
5. 同行政區＋同路段優先比價
6. 建物坪數 ±25% 優先匹配
7. 建物類型相近時提高權重
8. 計算成交平均／中位數／Q1／Q3
9. 計算目前在售物件開價相對市場的溢價／折價
10. 產生買方議價建議
11. 產生賣方定價建議
12. 產生市場判斷等級
13. 將結果輸出至 data/listing_comparison.json

注意：
本程式先獨立運作，不修改既有 analyzer.py / report.py / main.py。
"""

import csv
import json
import math
import os
import re
from datetime import datetime
from statistics import mean, median


# ============================================================
# 路徑設定
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LISTING_FILE = os.path.join(
    BASE_DIR,
    "data",
    "current_listings.csv"
)

TRANSACTION_FILE = os.path.join(
    BASE_DIR,
    "data",
    "taipei_transactions.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "data",
    "listing_comparison.json"
)


# ============================================================
# 基本工具
# ============================================================

def to_float(value):
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
        number = float(text)

        if math.isnan(number):
            return None

        return number

    except Exception:
        return None


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize_location(value):
    """
    統一路段名稱格式。

    例如：
    臺北市士林區中山北路五段
    → 中山北路五段
    """

    text = clean_text(value)

    if not text:
        return ""

    prefixes = [
        "臺北市士林區",
        "臺北市北投區",
        "台北市士林區",
        "台北市北投區",
        "臺北市",
        "台北市",
    ]

    for prefix in prefixes:
        text = text.replace(prefix, "")

    text = text.replace("臺北市", "")
    text = text.replace("台北市", "")

    return text.strip()


def extract_street(location):
    """
    從地址／位置文字抓出主要道路。

    例如：
    中山北路五段123號
    → 中山北路五段

    北科路
    → 北科路
    """

    text = normalize_location(location)

    if not text:
        return ""

    # 優先抓「路／街」及其後的段
    patterns = [
        r"(.+?路[一二三四五六七八九十0-9]*段)",
        r"(.+?街[一二三四五六七八九十0-9]*段)",
        r"(.+?大道[一二三四五六七八九十0-9]*段)",
        r"(.+?路)",
        r"(.+?街)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return match.group(1).strip()

    return text


def normalize_building_type(value):
    """
    將實價登錄建物類型簡化成：
    公寓 / 華廈 / 大樓 / 其他
    """

    text = clean_text(value)

    if not text:
        return "未知"

    if "公寓" in text:
        return "公寓"

    if "華廈" in text:
        return "華廈"

    if "大樓" in text:
        return "大樓"

    if "透天" in text:
        return "透天"

    return "其他"


def roc_date_to_iso(value):
    """
    實價資料 sdate 通常為民國年月日，例如：
    1150715 → 2026-07-15
    """

    text = clean_text(value)

    if not text:
        return ""

    # 已經是西元日期
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", text):
        try:
            return datetime.strptime(
                text,
                "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
        except Exception:
            return ""

    digits = re.sub(r"\D", "", text)

    if len(digits) != 7:
        return ""

    try:
        year = int(digits[:3]) + 1911
        month = int(digits[3:5])
        day = int(digits[5:7])

        return datetime(
            year,
            month,
            day
        ).strftime("%Y-%m-%d")

    except Exception:
        return ""


def percentile(values, p):
    """
    簡單百分位數計算。
    """

    if not values:
        return None

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    index = (len(values) - 1) * p

    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return values[lower]

    weight = index - lower

    return (
        values[lower] * (1 - weight)
        + values[upper] * weight
    )


def round_number(value, digits=2):
    if value is None:
        return None

    return round(float(value), digits)


# ============================================================
# 讀取在售物件
# ============================================================

def load_listings():
    if not os.path.exists(LISTING_FILE):
        raise FileNotFoundError(
            f"找不到在售物件資料：{LISTING_FILE}"
        )

    listings = []

    with open(
        LISTING_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            status = clean_text(
                row.get("status")
            ).lower()

            # 只分析 active
            if status and status not in {
                "active",
                "在售",
                "有效"
            }:
                continue

            district = clean_text(
                row.get("district")
            )

            if district not in {
                "士林區",
                "北投區"
            }:
                continue

            area = to_float(
                row.get("building_area")
            )

            unit_price = to_float(
                row.get("unit_price")
            )

            if area is None or area <= 0:
                continue

            if unit_price is None or unit_price <= 0:
                continue

            location = clean_text(
                row.get("location")
            )

            listing = {
                "listing_id": clean_text(
                    row.get("listing_id")
                ),
                "district": district,
                "location": location,
                "street": extract_street(location),
                "title": clean_text(
                    row.get("title")
                ),
                "total_price": to_float(
                    row.get("total_price")
                ),
                "building_area": area,
                "unit_price": unit_price,
                "age": to_float(
                    row.get("age")
                ),
                "floor": to_float(
                    row.get("floor")
                ),
                "total_floors": to_float(
                    row.get("total_floors")
                ),
                "rooms": to_float(
                    row.get("rooms")
                ),
                "halls": to_float(
                    row.get("halls")
                ),
                "bathrooms": to_float(
                    row.get("bathrooms")
                ),
                "parking": clean_text(
                    row.get("parking")
                ),
                "source": clean_text(
                    row.get("source")
                ),
                "url": clean_text(
                    row.get("url")
                ),
                "updated_at": clean_text(
                    row.get("updated_at")
                ),
            }

            listings.append(listing)

    return listings


# ============================================================
# 讀取實價成交
# ============================================================

def load_transactions():
    if not os.path.exists(TRANSACTION_FILE):
        raise FileNotFoundError(
            f"找不到實價成交資料：{TRANSACTION_FILE}"
        )

    transactions = []

    with open(
        TRANSACTION_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            # 只使用買賣
            case_t = clean_text(
                row.get("case_t")
            )

            if case_t != "買賣":
                continue

            district = clean_text(
                row.get("district")
            )

            if district not in {
                "士林區",
                "北投區"
            }:
                continue

            # 純土地排除
            case_f = clean_text(
                row.get("case_f")
            )

            if case_f == "土地":
                continue

            area = to_float(
                row.get("farea")
            )

            unit_price = to_float(
                row.get("uprice")
            )

            if area is None or area <= 0:
                continue

            if unit_price is None or unit_price <= 0:
                continue

            building_type = normalize_building_type(
                row.get("buitype")
            )

            # 排除明顯不是住宅的類型
            if building_type == "其他":

                # 如果沒有建物類型，但明確有房地資料，
                # 保留作為 fallback 成交資料
                if "房地" not in case_f:
                    continue

            location = clean_text(
                row.get("location")
            )

            transaction = {
                "id": row.get("_id"),
                "district": district,
                "location": location,
                "street": extract_street(location),
                "building_type": building_type,
                "area": area,
                "unit_price": unit_price,
                "transaction_price": to_float(
                    row.get("tprice")
                ),
                "date": roc_date_to_iso(
                    row.get("sdate")
                ),
                "floor": row.get("build_l"),
                "total_floors": row.get("sbuild"),
                "rooms": row.get("build_r"),
                "parking_price": to_float(
                    row.get("pprice")
                ),
                "case_f": case_f,
                "building_name": clean_text(
                    row.get("build_name")
                ),
                "remark": clean_text(
                    row.get("rmnote")
                ),
            }

            transactions.append(transaction)

    return transactions


# ============================================================
# 成交匹配
# ============================================================

def area_difference_ratio(listing_area, transaction_area):
    if listing_area <= 0:
        return 999

    return abs(
        transaction_area - listing_area
    ) / listing_area


def transaction_score(listing, transaction):
    """
    比價評分：

    同行政區        +40
    同路段           +40
    坪數 ±10%        +25
    坪數 ±20%        +15
    坪數 ±25%        +5
    同建物類型       +20

    總分越高代表越適合當比較案例。
    """

    score = 0

    if listing["district"] == transaction["district"]:
        score += 40

    if (
        listing["street"]
        and transaction["street"]
        and listing["street"] == transaction["street"]
    ):
        score += 40

    area_ratio = area_difference_ratio(
        listing["building_area"],
        transaction["area"]
    )

    if area_ratio <= 0.10:
        score += 25

    elif area_ratio <= 0.20:
        score += 15

    elif area_ratio <= 0.25:
        score += 5

    else:
        return -1

    # 目前在售資料沒有 buitype，
    # 因此這裡先不強制比較建物類型。

    return score


def find_comparables(
    listing,
    transactions,
    max_results=12
):
    candidates = []

    for transaction in transactions:

        if transaction["district"] != listing["district"]:
            continue

        score = transaction_score(
            listing,
            transaction
        )

        if score < 0:
            continue

        candidates.append(
            (
                score,
                transaction
            )
        )

    # 分數高的優先
    candidates.sort(
        key=lambda x: (
            -x[0],
            area_difference_ratio(
                listing["building_area"],
                x[1]["area"]
            )
        )
    )

    return [
        {
            "score": score,
            "transaction": transaction
        }
        for score, transaction
        in candidates[:max_results]
    ]


# ============================================================
# 市場判斷
# ============================================================

def classify_market(premium):
    """
    premium：
    目前開價相對成交中位數的差距。

    例如：
    +0.10 = 高於市場 10%
    -0.05 = 低於市場 5%
    """

    if premium is None:
        return {
            "level": "無法判斷",
            "emoji": "⚪",
            "description": "成交樣本不足"
        }

    if premium <= -0.08:
        return {
            "level": "低於市場",
            "emoji": "🟢",
            "description": "目前開價低於附近成交行情，具備價格吸引力"
        }

    if premium <= 0.05:
        return {
            "level": "接近市場",
            "emoji": "🟡",
            "description": "目前開價大致落在附近成交行情合理範圍"
        }

    if premium <= 0.12:
        return {
            "level": "合理偏高",
            "emoji": "🟡",
            "description": "目前開價高於附近成交行情，仍有議價空間"
        }

    return {
        "level": "高於市場",
        "emoji": "🔴",
        "description": "目前開價明顯高於附近成交行情"
    }


def calculate_recommendations(
    listing,
    market_median,
    q1,
    q3,
    sample_count
):
    if market_median is None:
        return {
            "seller_price_low": None,
            "seller_price_high": None,
            "buyer_price_low": None,
            "buyer_price_high": None,
            "note": "成交樣本不足，暫不提供精確議價價格"
        }

    # 賣方：
    # 以 Q1～Q3 作為主要市場價格帶
    seller_low = q1
    seller_high = q3

    # 買方：
    # 以市場中位數附近向下 3%～8%
    buyer_low = market_median * 0.92
    buyer_high = market_median * 0.97

    # 樣本太少時降低語氣
    if sample_count < 3:
        note = "成交樣本偏少，建議搭配現場屋況、樓層與車位條件判斷"

    elif sample_count < 5:
        note = "成交樣本有限，可作初步議價參考"

    else:
        note = "成交樣本達基本比較門檻，可作為主要議價參考之一"

    return {
        "seller_price_low": round_number(
            seller_low
        ),
        "seller_price_high": round_number(
            seller_high
        ),
        "buyer_price_low": round_number(
            buyer_low
        ),
        "buyer_price_high": round_number(
            buyer_high
        ),
        "note": note
    }


# ============================================================
# 單一物件分析
# ============================================================

def analyze_listing(
    listing,
    transactions
):
    comparables = find_comparables(
        listing,
        transactions
    )

    prices = [
        item["transaction"]["unit_price"]
        for item in comparables
    ]

    if not prices:
        return {
            "listing": listing,
            "comparison": {
                "sample_count": 0,
                "market_average": None,
                "market_median": None,
                "q1": None,
                "q3": None,
                "premium_ratio": None,
                "premium_percent": None,
                "market": classify_market(None),
                "recommendations": calculate_recommendations(
                    listing,
                    None,
                    None,
                    None,
                    0
                ),
                "comparables": []
            }
        }

    market_average = mean(prices)
    market_median = median(prices)
    q1 = percentile(prices, 0.25)
    q3 = percentile(prices, 0.75)

    premium_ratio = (
        listing["unit_price"] - market_median
    ) / market_median

    premium_percent = premium_ratio * 100

    market = classify_market(
        premium_ratio
    )

    recommendations = calculate_recommendations(
        listing,
        market_median,
        q1,
        q3,
        len(prices)
    )

    comparable_rows = []

    for item in comparables:

        transaction = item["transaction"]

        comparable_rows.append(
            {
                "score": item["score"],
                "date": transaction["date"],
                "location": transaction["location"],
                "street": transaction["street"],
                "building_type": transaction["building_type"],
                "area": round_number(
                    transaction["area"]
                ),
                "unit_price": round_number(
                    transaction["unit_price"]
                ),
                "transaction_price": round_number(
                    transaction["transaction_price"]
                ),
                "building_name": transaction[
                    "building_name"
                ]
            }
        )

    return {
        "listing": listing,

        "comparison": {
            "sample_count": len(prices),

            "market_average": round_number(
                market_average
            ),

            "market_median": round_number(
                market_median
            ),

            "q1": round_number(
                q1
            ),

            "q3": round_number(
                q3
            ),

            "listing_unit_price": round_number(
                listing["unit_price"]
            ),

            "premium_ratio": round_number(
                premium_ratio,
                4
            ),

            "premium_percent": round_number(
                premium_percent
            ),

            "market": market,

            "recommendations": recommendations,

            "comparables": comparable_rows
        }
    }


# ============================================================
# 整體分析
# ============================================================

def build_report(
    listings,
    transactions
):
    results = []

    for listing in listings:

        result = analyze_listing(
            listing,
            transactions
        )

        results.append(result)

    # ========================================================
    # 市場摘要
    # ========================================================

    total = len(results)

    low_count = 0
    near_count = 0
    high_count = 0
    unknown_count = 0

    for result in results:

        level = result[
            "comparison"
        ][
            "market"
        ][
            "level"
        ]

        if level == "低於市場":
            low_count += 1

        elif level in {
            "接近市場",
            "合理偏高"
        }:
            near_count += 1

        elif level == "高於市場":
            high_count += 1

        else:
            unknown_count += 1

    return {
        "generated_at": datetime.now().astimezone().isoformat(),

        "stage": "第20階段：在售物件 × 實價成交比價引擎",

        "summary": {
            "listing_count": total,
            "transaction_count": len(
                transactions
            ),
            "below_market": low_count,
            "near_market": near_count,
            "above_market": high_count,
            "insufficient_sample": unknown_count
        },

        "results": results
    }


# ============================================================
# 儲存 JSON
# ============================================================

def save_report(report):

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "第20階段：在售物件 × 實價成交比價引擎"
    )
    print("=" * 70)

    print()
    print("讀取在售物件……")

    listings = load_listings()

    print(
        f"在售物件：{len(listings)} 筆"
    )

    print()
    print("讀取實價成交資料……")

    transactions = load_transactions()

    print(
        f"有效住宅買賣成交："
        f"{len(transactions)} 筆"
    )

    print()
    print("開始進行市場比價……")

    report = build_report(
        listings,
        transactions
    )

    save_report(report)

    print()
    print("=" * 70)
    print("第20階段完成")
    print("=" * 70)

    print()
    print(
        f"在售物件："
        f"{report['summary']['listing_count']} 筆"
    )

    print(
        f"成交比較資料："
        f"{report['summary']['transaction_count']} 筆"
    )

    print(
        f"🟢 低於市場："
        f"{report['summary']['below_market']} 筆"
    )

    print(
        f"🟡 接近／合理偏高："
        f"{report['summary']['near_market']} 筆"
    )

    print(
        f"🔴 高於市場："
        f"{report['summary']['above_market']} 筆"
    )

    print(
        f"⚪ 樣本不足："
        f"{report['summary']['insufficient_sample']} 筆"
    )

    print()
    print(
        f"輸出檔案：{OUTPUT_FILE}"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
