# -*- coding: utf-8 -*-

"""
第35階段：房仲實戰價格決策引擎 V6.1.2
A/B/C 正式估價＋D行情參考＋E/F排除＋樣本不足顯示修正版

功能：

1. 讀取目前在售物件
   data/current_listings.csv

2. 優先讀取 591 歷史成交
   data/591_transactions.csv

3. 再讀取內政部／既有實價資料
   data/taipei_transactions.csv

4. 自動尋找可比成交：
   A. 同門牌＋同樓層
   B. 同門牌
   C. 同路段＋相近坪數＋同類型
   D. 同路段／同區＋較寬坪數＋同類型
   E. 同行政區＋相近坪數
    F. 同行政區＋較寬坪數（最後保底）

5. 先取最多 24 筆候選，過濾異常值後最多保留 12 筆有效可比成交

6. 正式估價僅使用 A/B/C；D 僅作行情參考；E/F 不得進入正式價格計算

7. 3～12 筆：
   使用中位數＋加權中位數
   建立合理價格區間

8. 輸出：
   data/pricing_decisions.csv

9. V6.1：正式樣本不足時，weighted_market_unit_price 不列為正式市場價格；
   另以 market_reference_unit_price 與 market_reference_note 保存內部參考資訊。
"""

import csv
import math
import os
import re
from datetime import date
from statistics import median


# ============================================================
# 基本路徑
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATA_DIR = os.path.join(
    BASE_DIR,
    "data"
)

LISTING_FILE = os.path.join(
    DATA_DIR,
    "current_listings.csv"
)

TRANSACTION_FILES = [
    os.path.join(
        DATA_DIR,
        "591_transactions.csv"
    ),
    os.path.join(
        DATA_DIR,
        "taipei_transactions.csv"
    ),
]

OUTPUT_FILE = os.path.join(
    DATA_DIR,
    "pricing_decisions.csv"
)


# ============================================================
# 參數
# ============================================================

MIN_COMPARABLES = 3
MAX_COMPARABLES = 12

# 第31階段：多層級擴充與異常值過濾
# 只有樣本數足夠時才啟動統計型異常值過濾，避免小樣本被過度刪除。
OUTLIER_MIN_SAMPLE = 5
OUTLIER_MAD_Z = 3.5
OUTLIER_IQR_FACTOR = 1.5


# ============================================================
# 輸出欄位
# 保留原本 pricing_decisions.csv 格式
# ============================================================

OUTPUT_FIELDS = [
    "listing_id",
    "district",
    "location",
    "title",
    "current_price",
    "current_unit_price",
    "comparable_count",
    "median_transaction_price",
    "median_transaction_unit_price",
    "price_gap_percent",
    "reasonable_low_price",
    "reasonable_high_price",
    "buyer_first_price",
    "buyer_max_price",
    "seller_reasonable_price",
    "negotiation_percent",
    "price_grade",
    "confidence",
    "core_comparable_count",
    "grade_a_count",
    "grade_b_count",
    "grade_c_count",
    "grade_d_count",
    "grade_e_count",
    "extension_comparable_count",
    "excluded_count",
    "excluded_reasons",
    "weighted_market_unit_price",
    "market_reference_unit_price",
    "market_reference_note",
    "comparable_grade_summary",
]


# ============================================================
# 基本工具
# ============================================================

def text(value):
    if value is None:
        return ""

    return str(value).strip()


def num(value):
    if value is None:
        return None

    value = text(value)

    if not value:
        return None

    try:
        value = (
            value
            .replace(",", "")
            .replace("萬", "")
        )

        return float(value)

    except (TypeError, ValueError):
        return None


def normalize_text(value):
    value = text(value)

    value = value.replace(
        "臺",
        "台"
    )

    value = re.sub(
        r"\s+",
        "",
        value
    )

    return value


# ============================================================
# 中文樓層
# ============================================================

def chinese_floor_to_int(value):

    mapping = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }

    value = text(value)

    if not value:
        return None

    if value in mapping:
        return mapping[value]

    # 十一、十二
    if (
        len(value) == 2
        and value[0] == "十"
        and value[1] in mapping
    ):
        return 10 + mapping[value[1]]

    # 二十
    if (
        len(value) == 2
        and value[1] == "十"
        and value[0] in mapping
    ):
        return mapping[value[0]] * 10

    # 二十一
    if (
        len(value) == 3
        and value[1] == "十"
        and value[0] in mapping
        and value[2] in mapping
    ):
        return (
            mapping[value[0]] * 10
            + mapping[value[2]]
        )

    return None


# ============================================================
# 樓層解析
# ============================================================

def floor_number(value):

    value = normalize_text(
        value
    ).upper()

    if not value:
        return None

    match = re.search(
        r"(\d+)\s*(?:F|樓|層)",
        value
    )

    if match:
        return int(
            match.group(1)
        )

    match = re.search(
        r"([一二三四五六七八九十]+)\s*(?:樓|層)",
        value
    )

    if match:
        return chinese_floor_to_int(
            match.group(1)
        )

    if value.isdigit():
        return int(value)

    return None


# ============================================================
# 地址標準化
# ============================================================

def address_key(value):

    value = normalize_text(
        value
    )

    if not value:
        return ""

    # 去除樓層
    value = re.sub(
        r"[0-9]+\s*樓(?:之[0-9]+)?",
        "",
        value,
        flags=re.I
    )

    value = re.sub(
        r"[一二三四五六七八九十]+\s*樓"
        r"(?:之[一二三四五六七八九十0-9]+)?",
        "",
        value
    )

    # 只抓主要門牌
    match = re.search(
        r"(.+?\d+號)",
        value
    )

    if match:
        return match.group(1)

    return value


# ============================================================
# 路段解析
# ============================================================

def street_key(value):

    value = normalize_text(
        value
    )

    if not value:
        return ""

    match = re.search(
        r"([\u4e00-\u9fff]{2,12}"
        r"(?:路|街|大道)"
        r"(?:[一二三四五六七八九十0-9]+段)?)",
        value
    )

    if match:
        return match.group(1)

    return ""


def street_family(value):
    """將同一路名不同段別歸為同一街道家族，例如中山北路五段/六段。"""
    street = street_key(value)
    if not street:
        return ""

    return re.sub(
        r"[一二三四五六七八九十0-9]+段$",
        "",
        street
    )


def same_street_family(listing, transaction):
    left = street_family(listing.get("location"))
    right = transaction.get("street_family") or street_family(transaction.get("location"))
    return bool(left and right and left == right)


# ============================================================
# 日期解析
# ============================================================

def date_key(value):

    value = text(value)

    if not value:
        return None

    # --------------------------------------------------------
    # 民國日期
    # 例如：
    # 1150612
    # --------------------------------------------------------

    match = re.search(
        r"^(\d{3})(\d{2})(\d{2})$",
        value
    )

    if match:

        year = (
            int(match.group(1))
            + 1911
        )

        month = int(
            match.group(2)
        )

        day = int(
            match.group(3)
        )

        try:
            return date(
                year,
                month,
                min(day, 28)
            )

        except ValueError:
            return None

    # --------------------------------------------------------
    # 西元日期
    # --------------------------------------------------------

    match = re.search(
        r"(\d{4})[-/]?"
        r"(\d{1,2})"
        r"(?:[-/]?(\d{1,2}))?",
        value
    )

    if match:

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        day = int(
            match.group(3) or 1
        )

        if not 1 <= month <= 12:
            return None

        try:
            return date(
                year,
                month,
                min(day, 28)
            )

        except ValueError:
            return None

    return None


# ============================================================
# 成交時間權重
# 越新的成交權重越高
# ============================================================

def recency_weight(transaction_date):

    if not transaction_date:
        return 0.55

    days = max(
        0,
        (
            date.today()
            - transaction_date
        ).days
    )

    return max(
        0.55,
        math.exp(
            -days / 730.0
        )
    )


# ============================================================
# 建物型態分類
# ============================================================

def type_family(value):

    value = normalize_text(
        value
    )

    if any(
        item in value
        for item in (
            "透天",
            "別墅",
        )
    ):
        return "透天"

    if "公寓" in value:
        return "公寓"

    if "華廈" in value:
        return "華廈"

    if (
        "大樓" in value
        or "住宅大樓" in value
    ):
        return "大樓"

    return "其他"


# ============================================================
# 車位判斷
# ============================================================

def parking_flag(value):

    value = normalize_text(
        value
    )

    if not value:
        return None

    if any(
        item in value
        for item in (
            "無",
            "沒有",
            "無車位",
        )
    ):
        return False

    return True


# ============================================================
# CSV
# ============================================================

def read_csv(path):

    if not os.path.exists(path):
        return []

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(
            file
        )

        return list(reader)


# ============================================================
# 讀取在售物件
# ============================================================

def load_listings():

    rows = read_csv(
        LISTING_FILE
    )

    listings = []

    for row in rows:

        total_price = num(
            row.get(
                "total_price"
            )
        )

        area = num(
            row.get(
                "building_area"
            )
        )

        unit_price = num(
            row.get(
                "unit_price"
            )
        )

        if (
            not total_price
            or not area
            or area <= 0
        ):
            continue

        if (
            not unit_price
            or unit_price <= 0
        ):
            unit_price = (
                total_price
                / area
            )

        listings.append({

            "listing_id":
                text(
                    row.get(
                        "listing_id"
                    )
                ),

            "district":
                normalize_text(
                    row.get(
                        "district"
                    )
                ),

            "location":
                text(
                    row.get(
                        "location"
                    )
                ),

            "title":
                text(
                    row.get(
                        "title"
                    )
                ),

            "price":
                total_price,

            "area":
                area,

            "unit":
                unit_price,

            "age":
                num(
                    row.get(
                        "age"
                    )
                ),

            "floor":
                floor_number(
                    row.get(
                        "floor"
                    )
                )
                or floor_number(
                    row.get(
                        "location"
                    )
                ),

            "total_floors":
                num(
                    row.get(
                        "total_floors"
                    )
                ),

            "rooms":
                num(
                    row.get(
                        "rooms"
                    )
                ),

            "parking":
                parking_flag(
                    row.get(
                        "parking"
                    )
                ),

            "type":
                type_family(
                    row.get(
                        "building_type"
                    )
                    or row.get(
                        "buitype"
                    )
                    or row.get(
                        "title"
                    )
                ),
        })

    return listings


# ============================================================
# 讀取成交資料
# ============================================================

def load_transactions():

    transactions = []

    seen = set()

    for path in TRANSACTION_FILES:

        rows = read_csv(
            path
        )

        for row in rows:

            district = normalize_text(
                row.get(
                    "district"
                )
            )

            # ------------------------------------------------
            # 面積
            # ------------------------------------------------

            area = num(
                row.get(
                    "building_area"
                )
            )

            if area is None:
                area = num(
                    row.get(
                        "farea"
                    )
                )

            # ------------------------------------------------
            # 單價
            # ------------------------------------------------

            unit_price = num(
                row.get(
                    "unit_price"
                )
            )

            if unit_price is None:
                unit_price = num(
                    row.get(
                        "uprice"
                    )
                )

            # ------------------------------------------------
            # 總價
            # ------------------------------------------------

            total_price = num(
                row.get(
                    "total_price"
                )
            )

            if total_price is None:
                total_price = num(
                    row.get(
                        "tprice"
                    )
                )

            # ------------------------------------------------
            # 基本資料檢查
            # ------------------------------------------------

            if (
                not district
                or not area
                or area <= 0
                or not unit_price
                or unit_price <= 0
            ):
                continue

            # ------------------------------------------------
            # 交易類型
            # ------------------------------------------------

            case_type = normalize_text(
                row.get(
                    "case_type"
                )
                or row.get(
                    "case_t"
                )
            )

            if (
                case_type
                and "買賣" not in case_type
            ):
                continue

            # ------------------------------------------------
            # 排除土地、純車位
            # ------------------------------------------------

            case_f = normalize_text(
                row.get(
                    "case_f"
                )
            )

            if case_f == "車位":
                continue

            if (
                case_f
                and "土地" in case_f
                and "房" not in case_f
            ):
                continue

            # ------------------------------------------------
            # 地址
            # ------------------------------------------------

            location = text(
                row.get(
                    "address"
                )
                or row.get(
                    "location"
                )
            )

            # ------------------------------------------------
            # 日期
            # ------------------------------------------------

            transaction_date = date_key(
                row.get(
                    "transaction_date"
                )
                or row.get(
                    "sdate"
                )
                or row.get(
                    "fdate"
                )
            )

            # ------------------------------------------------
            # ID
            # ------------------------------------------------

            transaction_id = text(
                row.get(
                    "transaction_id"
                )
                or row.get(
                    "_id"
                )
            )

            # ------------------------------------------------
            # 去除重複資料
            # ------------------------------------------------

            unique_key = (
                transaction_id,
                district,
                location,
                area,
                unit_price,
                total_price,
                text(
                    row.get(
                        "transaction_date"
                    )
                    or row.get(
                        "sdate"
                    )
                ),
            )

            if (
                transaction_id
                and unique_key in seen
            ):
                continue

            seen.add(
                unique_key
            )

            source = "591"

            if (
                "591_transactions"
                not in os.path.basename(
                    path
                )
            ):
                source = "MOI"

            special = special_transaction_info(row)

            if special["excluded"]:
                continue

            transactions.append({

                "id":
                    transaction_id,

                "source":
                    source,

                "district":
                    district,

                "location":
                    location,

                "address":
                    address_key(
                        location
                    ),

                "street":
                    street_key(
                        location
                    ),

                "street_family":
                    street_family(
                        location
                    ),

                "area":
                    area,

                "unit":
                    unit_price,

                "price":
                    total_price,

                "floor":
                    floor_number(
                        row.get(
                            "floor"
                        )
                    )
                    or floor_number(
                        location
                    ),

                "total_floors":
                    num(
                        row.get(
                            "total_floors"
                        )
                    ),

                "age":
                    num(
                        row.get("age")
                        or row.get("build_age")
                        or row.get("building_age")
                    ),

                "type":
                    type_family(
                        row.get(
                            "building_type"
                        )
                        or row.get(
                            "buitype"
                        )
                    ),

                "parking":
                    parking_flag(
                        row.get(
                            "parking"
                        )
                        or row.get(
                            "parktype"
                        )
                    ),

                "date":
                    transaction_date,

                "related":
                    special["related"],

                "special":
                    special["special"],

                "expansion":
                    special["expansion"],

                "pre_sale":
                    special["pre_sale"],
            })

    return transactions


# ============================================================
# V4：特殊交易／異常資料判斷
# ============================================================

def special_transaction_info(row):
    """判斷關係人、特殊交易、增建等風險訊號。"""
    values = []
    for key in (
        "note", "remark", "remarks", "memo", "case_remark",
        "case_note", "case_f", "case_t", "case_type",
        "building_type", "buitype", "parktype"
    ):
        values.append(normalize_text(row.get(key)))
    blob = "|".join(v for v in values if v)

    relation = any(x in blob for x in ("關係人", "親友", "二親等", "三親等"))
    special = any(x in blob for x in ("特殊交易", "親友交易", "特殊關係", "毛胚", "毛坯"))
    expansion = any(x in blob for x in ("陽台外推", "增建", "未保存登記", "頂樓加蓋"))
    pre_sale = any(x in blob for x in ("預售", "預售屋", "讓渡"))
    land_only = normalize_text(row.get("case_f")) in ("土地", "車位")

    return {
        "related": relation,
        "special": special,
        "expansion": expansion,
        "pre_sale": pre_sale,
        "excluded": land_only,
    }


def confidence_from_comparables(comparables):
    """依採用的可比層級與樣本數判斷信心。"""
    if not comparables:
        return "低"

    a = sum(1 for x in comparables if x["tier"] == "A")
    b = sum(1 for x in comparables if x["tier"] == "B")
    c = sum(1 for x in comparables if x["tier"] == "C")
    n = len(comparables)

    if a + b >= 3 and n >= 3:
        return "高"

    if a + b + c >= 3 and n >= 3:
        return "中高"

    if a + b + c + sum(1 for x in comparables if x["tier"] == "D") >= 3:
        return "中"

    if n >= 3:
        return "中低"

    return "低"


def _match_exclusion_reason(listing, transaction):
    """回傳此成交未進入可比樣本的主要原因。"""
    if transaction["district"] != listing["district"]:
        return "不同行政區"

    if transaction.get("related"):
        return "關係人交易"

    if transaction.get("special"):
        return "特殊交易"

    if transaction.get("pre_sale"):
        return "預售／讓渡"

    area_ratio = abs(transaction["area"] - listing["area"]) / listing["area"]
    if area_ratio > 0.60:
        return "坪數差異>60%"

    return None


# ============================================================
# V4 成交匹配
# ============================================================

def score_transaction(listing, transaction):
    """
    第31階段多層級可比：
    A 同門牌＋同樓層
    B 同門牌
    C 同路段＋相近坪數＋同類型
    D 同路段／同街道家族＋較寬坪數＋同類型
    E 同行政區＋相近坪數
    F 同行政區＋較寬坪數（最後擴充層）

    注意：
    F 是「最後保底擴充」，不代表高品質同類型案例。
    """

    if transaction["district"] != listing["district"]:
        return None

    if (
        transaction.get("related")
        or transaction.get("special")
        or transaction.get("pre_sale")
    ):
        return None

    area_ratio = abs(
        transaction["area"] - listing["area"]
    ) / listing["area"]

    if area_ratio > 0.60:
        return None

    same_address = (
        bool(listing["location"])
        and bool(transaction["address"])
        and address_key(listing["location"]) == transaction["address"]
    )

    same_floor = (
        listing["floor"] is not None
        and transaction["floor"] is not None
        and listing["floor"] == transaction["floor"]
    )

    same_street = (
        bool(street_key(listing["location"]))
        and bool(transaction["street"])
        and street_key(listing["location"]) == transaction["street"]
    )

    same_family = same_street_family(listing, transaction)

    same_type = (
        listing["type"] == "其他"
        or transaction["type"] == "其他"
        or listing["type"] == transaction["type"]
    )

    parking_same = (
        listing["parking"] is None
        or transaction["parking"] is None
        or listing["parking"] == transaction["parking"]
    )

    if same_address and same_floor:
        tier = "A"
        base_weight = 2.80
    elif same_address:
        tier = "B"
        base_weight = 2.00
    elif same_street and area_ratio <= 0.20 and same_type:
        tier = "C"
        base_weight = 1.45
    elif same_street and area_ratio <= 0.30 and same_type:
        tier = "D"
        base_weight = 0.90
    elif same_family and area_ratio <= 0.30 and same_type:
        tier = "D"
        base_weight = 0.72
    elif area_ratio <= 0.30 and same_type:
        tier = "E"
        base_weight = 0.52
    elif area_ratio <= 0.40:
        tier = "E"
        base_weight = 0.34
    elif area_ratio <= 0.60 and same_type:
        tier = "F"
        base_weight = 0.22
    else:
        return None

    expansion_factor = 0.55 if transaction.get("expansion") else 1.0
    type_factor = 1.0 if same_type else 0.68
    parking_factor = 1.0 if parking_same else 0.88
    area_factor = max(0.50, 1.0 - area_ratio * 1.20)

    floor_factor = 1.0
    if listing["floor"] is not None and transaction["floor"] is not None:
        floor_difference = abs(
            listing["floor"] - transaction["floor"]
        )
        floor_factor = max(
            0.78,
            1.0 - floor_difference * 0.025
        )

    age_factor = 1.0
    if listing.get("age") is not None and transaction.get("age") is not None:
        age_difference = abs(
            listing["age"] - transaction["age"]
        )
        age_factor = max(
            0.68,
            1.0 - age_difference * 0.022
        )

    time_factor = recency_weight(transaction["date"])
    source_factor = (
        1.08
        if transaction.get("source") == "591"
        else 1.0
    )

    final_weight = (
        base_weight
        * type_factor
        * parking_factor
        * area_factor
        * floor_factor
        * age_factor
        * time_factor
        * expansion_factor
        * source_factor
    )

    return {
        "score": round(final_weight * 100, 2),
        "weight": final_weight,
        "tier": tier,
        "same_address": same_address,
        "same_floor": same_floor,
        "same_street": same_street,
        "same_family": same_family,
        "area_ratio": area_ratio,
        "adjusted_unit": transaction["unit"] * floor_factor,
        "tx": transaction,
    }


def filter_outliers(comparables):
    """
    第31階段：統計型異常值過濾。

    - <5筆：不做統計刪除，避免小樣本誤殺。
    - >=5筆：以 MAD 為主，IQR 為輔。
    - 每次至少保留 3 筆；若過濾後不足 3 筆，回復原樣。
    """
    if len(comparables) < OUTLIER_MIN_SAMPLE:
        return list(comparables), []

    values = [
        float(item["adjusted_unit"])
        for item in comparables
        if item.get("adjusted_unit") is not None
    ]

    if len(values) < OUTLIER_MIN_SAMPLE:
        return list(comparables), []

    med = median(values)
    deviations = [abs(v - med) for v in values]
    mad = median(deviations)

    sorted_values = sorted(values)
    q1_index = (len(sorted_values) - 1) * 0.25
    q3_index = (len(sorted_values) - 1) * 0.75

    def percentile(data, pos):
        low = int(pos)
        high = min(low + 1, len(data) - 1)
        frac = pos - low
        return data[low] + (data[high] - data[low]) * frac

    q1 = percentile(sorted_values, q1_index)
    q3 = percentile(sorted_values, q3_index)
    iqr = q3 - q1

    low_iqr = q1 - OUTLIER_IQR_FACTOR * iqr
    high_iqr = q3 + OUTLIER_IQR_FACTOR * iqr

    kept = []
    removed = []

    for item in comparables:
        value = float(item["adjusted_unit"])

        mad_outlier = False
        if mad > 0:
            robust_z = 0.6745 * (value - med) / mad
            mad_outlier = abs(robust_z) > OUTLIER_MAD_Z

        iqr_outlier = (
            iqr > 0
            and (value < low_iqr or value > high_iqr)
        )

        # 兩種方法同意才排除，避免把真實高低價誤判成異常。
        if mad_outlier and iqr_outlier:
            removed.append(item)
        else:
            kept.append(item)

    if len(kept) < MIN_COMPARABLES:
        return list(comparables), []

    return kept, removed


# ============================================================
# 找可比成交＋排除原因
# ============================================================

def find_comparables(listing, transactions):
    scored = []
    exclusion_counts = {}

    for transaction in transactions:
        reason = _match_exclusion_reason(listing, transaction)
        if reason:
            exclusion_counts[reason] = exclusion_counts.get(reason, 0) + 1
            continue

        result = score_transaction(listing, transaction)

        if result:
            scored.append(result)
        else:
            area_ratio = abs(
                transaction["area"] - listing["area"]
            ) / listing["area"]

            if area_ratio > 0.60:
                reason = "坪數差異>60%"
            elif (
                listing["type"] != "其他"
                and transaction["type"] != "其他"
                and listing["type"] != transaction["type"]
            ):
                reason = "建物型態不同"
            else:
                reason = "未達可比條件"

            exclusion_counts[reason] = (
                exclusion_counts.get(reason, 0) + 1
            )

    scored.sort(
        key=lambda item: (
            -item["score"],
            -(
                item["tx"]["date"].toordinal()
                if item["tx"]["date"]
                else 0
            ),
        )
    )

    # 先保留最多 24 筆，讓第31階段有足夠樣本做異常值過濾。
    scored = scored[:24]

    unique = []
    seen = set()

    for item in scored:
        tx = item["tx"]
        key = (
            tx["district"],
            tx["address"],
            tx["area"],
            tx["unit"],
            tx["date"],
        )

        if key in seen:
            exclusion_counts["重複成交"] = (
                exclusion_counts.get("重複成交", 0) + 1
            )
            continue

        seen.add(key)
        unique.append(item)

    filtered, removed = filter_outliers(unique)

    if removed:
        exclusion_counts["統計異常值"] = (
            exclusion_counts.get("統計異常值", 0)
            + len(removed)
        )

    # 保留過濾前的最高品質排序。
    filtered.sort(
        key=lambda item: (
            -item["score"],
            -(
                item["tx"]["date"].toordinal()
                if item["tx"]["date"]
                else 0
            ),
        )
    )

    return filtered[:MAX_COMPARABLES], exclusion_counts


# ============================================================
# 金額格式
# ============================================================

# ============================================================
# 加權中位數
# ============================================================

def weighted_median(
    values_weights
):

    data = sorted(
        values_weights,
        key=lambda item: item[0]
    )

    total_weight = sum(
        max(
            0.0001,
            weight
        )
        for value, weight
        in data
    )

    accumulated = 0.0

    for value, weight in data:

        accumulated += max(
            0.0001,
            weight
        )

        if (
            accumulated
            >= total_weight / 2
        ):
            return value

    if data:
        return data[-1][0]

    return None


# ============================================================
# 金額格式
# ============================================================

def money(value):

    if value is None:
        return None

    return round(
        value,
        2
    )


# ============================================================
# 樣本不足
# ============================================================

def make_empty_decision(listing):
    return {
        "listing_id": listing["listing_id"],
        "district": listing["district"],
        "location": listing["location"],
        "title": listing["title"],
        "current_price": money(listing["price"]),
        "current_unit_price": money(listing["unit"]),
        "comparable_count": 0,
        "median_transaction_price": None,
        "median_transaction_unit_price": None,
        "price_gap_percent": None,
        "reasonable_low_price": None,
        "reasonable_high_price": None,
        "buyer_first_price": None,
        "buyer_max_price": None,
        "seller_reasonable_price": None,
        "negotiation_percent": None,
        "price_grade": "樣本不足",
        "confidence": "低",
        "core_comparable_count": 0,
        "grade_a_count": 0,
        "grade_b_count": 0,
        "grade_c_count": 0,
        "grade_d_count": 0,
        "grade_e_count": 0,
        "extension_comparable_count": 0,
        "excluded_count": 0,
        "excluded_reasons": "",
        "weighted_market_unit_price": None,
        "market_reference_unit_price": None,
        "market_reference_note": "無可用正式樣本；不提供市場價格參考。",
        "comparable_grade_summary": "A0/B0/C0/D0/E0",
    }


# ============================================================
# 單一物件決策
# ============================================================

def decision_for_listing(listing, transactions):
    comparables, exclusion_counts = find_comparables(
        listing,
        transactions
    )

    current_price = listing["price"]
    current_unit = listing["unit"]

    a_count = sum(1 for x in comparables if x["tier"] == "A")
    b_count = sum(1 for x in comparables if x["tier"] == "B")
    c_count = sum(1 for x in comparables if x["tier"] == "C")
    d_count = sum(1 for x in comparables if x["tier"] == "D")
    e_count = sum(1 for x in comparables if x["tier"] == "E")
    f_count = sum(1 for x in comparables if x["tier"] == "F")

    # ========================================================
    # V6：統一正式估價規則
    #
    # A/B：最高品質核心樣本
    # C：可納入正式估價，但降低信心
    # D：僅作行情參考
    # E/F：完全不得進入正式價格計算
    #
    # 正式估價至少需要 A+B+C 合計 3 筆。
    # ========================================================

    core_count = a_count + b_count + c_count

    if a_count + b_count >= 3:
        selected = [
            x for x in comparables
            if x["tier"] in ("A", "B")
        ]
        sample_mode = "正式核心A/B"

    elif core_count >= 3:
        selected = [
            x for x in comparables
            if x["tier"] in ("A", "B", "C")
        ]
        sample_mode = "正式核心A/B/C"

    else:
        # A/B/C 不足 3 筆：
        # 只保留 A/B/C 作為行情參考，
        # D/E/F 不得進入正式價格計算。
        selected = [
            x for x in comparables
            if x["tier"] in ("A", "B", "C")
        ]
        sample_mode = "正式樣本不足"

    # 若同級樣本很多，仍保留最高分的12筆
    selected = sorted(
        selected,
        key=lambda item: -item["score"]
    )[:MAX_COMPARABLES]

    comparable_count = len(selected)

    excluded_reasons = "; ".join(
        f"{k}:{v}"
        for k, v in sorted(
            exclusion_counts.items(),
            key=lambda item: (-item[1], item[0])
        )[:8]
    )

    grade_summary = (
        f"A{a_count}/B{b_count}/C{c_count}/"
        f"D{d_count}/E{e_count}/F{f_count}"
    )

    extension_count = c_count + d_count + e_count + f_count
    confidence = confidence_from_comparables(selected)

    if not selected:
        result = make_empty_decision(listing)
        result.update({
            "grade_a_count": a_count,
            "grade_b_count": b_count,
            "grade_c_count": c_count,
            "grade_d_count": d_count,
            "grade_e_count": e_count,
            "extension_comparable_count": extension_count,
            "excluded_count": sum(exclusion_counts.values()),
            "excluded_reasons": excluded_reasons,
            "comparable_grade_summary": grade_summary,
        })
        return result

    adjusted_units = [
        item["adjusted_unit"]
        for item in selected
    ]
    weights = [
        item["weight"]
        for item in selected
    ]
    transaction_totals = [
        item["tx"]["price"]
        for item in selected
        if item["tx"]["price"]
        and item["tx"]["price"] > 0
    ]

    median_unit = median(adjusted_units)
    weighted_unit = weighted_median(
        list(zip(adjusted_units, weights))
    )

    median_total = (
        median(transaction_totals)
        if transaction_totals
        else None
    )

    # ========================================================
    # V6：正式估價權重
    #
    # A/B：最高品質
    # A/B/C：正式估價，但 C 的權重較低
    # D/E/F 不會進入 selected，因此不得影響正式價格。
    # ========================================================

    if sample_mode == "正式核心A/B":
        weighted_ratio = 0.80
    elif sample_mode == "正式核心A/B/C":
        weighted_ratio = 0.75
    else:
        weighted_ratio = 0.70

    fair_unit = (
        weighted_unit * weighted_ratio
        + median_unit * (1 - weighted_ratio)
    )

    fair_price = fair_unit * listing["area"]

    # ========================================================
    # V6.1.2：正式價格與內部參考價格分離
    # V6：正式樣本不足
    #
    # A/B/C 不足 3 筆：
    # 不輸出正式合理價格、買方價、賣方價。
    # 僅保留市場參考統計。
    # ========================================================

    if (
        core_count < MIN_COMPARABLES
        or comparable_count < MIN_COMPARABLES
    ):
        price_gap = (
            ((current_unit / fair_unit) - 1) * 100
            if fair_unit
            else None
        )

        return {
            "listing_id": listing["listing_id"],
            "district": listing["district"],
            "location": listing["location"],
            "title": listing["title"],
            "current_price": money(current_price),
            "current_unit_price": money(current_unit),
            "comparable_count": comparable_count,
            "median_transaction_price": money(median_total),
            "median_transaction_unit_price": money(median_unit),
            "price_gap_percent": money(price_gap),

            "reasonable_low_price": None,
            "reasonable_high_price": None,
            "buyer_first_price": None,
            "buyer_max_price": None,
            "seller_reasonable_price": None,
            "negotiation_percent": None,

            "price_grade": "樣本不足",
            "confidence": "低",

            "core_comparable_count": core_count,
            "grade_a_count": a_count,
            "grade_b_count": b_count,
            "grade_c_count": c_count,
            "grade_d_count": d_count,
            "grade_e_count": e_count,
            "extension_comparable_count": extension_count,

            "excluded_count": sum(exclusion_counts.values()),
            "excluded_reasons": excluded_reasons,

            # V6.1：樣本不足時，不能把統計結果放在正式市場價格欄位。
            # 保留計算值供內部追蹤，但明確標示為參考值，不列入正式估價。
            "weighted_market_unit_price": None,
            "market_reference_unit_price": money(weighted_unit),
            "market_reference_note": (
                "V6.1.2：正式樣本不足；市場參考單價僅供內部參考，絕不列入正式估價。僅有 "
                f"{comparable_count} 筆 A/B/C 可比樣本。"
            ),
            "comparable_grade_summary": grade_summary,
        }

    # 擴充樣本越多，仍保留較寬的估價區間
    if sample_mode == "正式核心A/B" and comparable_count >= 4:
        spread = 0.10
    elif sample_mode == "正式核心A/B/C":
        spread = 0.12
    elif sample_mode == "核心＋D擴充":
        spread = 0.15
    elif sample_mode == "核心＋E擴充":
        spread = 0.18
    else:
        spread = 0.20

    if confidence in ("低", "中低"):
        spread += 0.03

    low_unit = fair_unit * (1 - spread)
    high_unit = fair_unit * (1 + spread)

    low_price = low_unit * listing["area"]
    high_price = high_unit * listing["area"]

    buyer_first_price = low_price * 0.95
    buyer_max_price = high_price * 0.98
    seller_reasonable_price = high_price

    negotiation_percent = max(
        0.0,
        ((current_price - buyer_max_price) / current_price) * 100
    )

    price_gap_percent = (
        ((current_unit / fair_unit) - 1) * 100
    )

    if price_gap_percent >= 15:
        price_grade = "價格過高"
    elif price_gap_percent >= 7:
        price_grade = "偏高"
    elif price_gap_percent <= -7:
        price_grade = "價格偏低"
    else:
        price_grade = "接近市場"

    # 明確提醒擴充樣本占比過高
    if sample_mode != "正式核心A/B" and price_grade == "接近市場":
        price_grade = "接近市場（擴充樣本）"

    # 低信心即使達到3筆，也避免給出過度精準的訊號。
    if confidence == "低":
        price_grade = "樣本偏弱－僅供參考"

    return {
        "listing_id": listing["listing_id"],
        "district": listing["district"],
        "location": listing["location"],
        "title": listing["title"],
        "current_price": money(current_price),
        "current_unit_price": money(current_unit),
        "comparable_count": comparable_count,
        "median_transaction_price": money(median_total),
        "median_transaction_unit_price": money(median_unit),
        "price_gap_percent": money(price_gap_percent),
        "reasonable_low_price": money(low_price),
        "reasonable_high_price": money(high_price),
        "buyer_first_price": money(buyer_first_price),
        "buyer_max_price": money(buyer_max_price),
        "seller_reasonable_price": money(seller_reasonable_price),
        "negotiation_percent": money(negotiation_percent),
        "price_grade": price_grade,
        "confidence": confidence,
        "core_comparable_count": core_count,
        "grade_a_count": a_count,
        "grade_b_count": b_count,
        "grade_c_count": c_count,
        "grade_d_count": d_count,
        "grade_e_count": e_count,
        "extension_comparable_count": extension_count,
        "excluded_count": sum(exclusion_counts.values()),
        "excluded_reasons": excluded_reasons,
        "weighted_market_unit_price": money(weighted_unit),
        "market_reference_unit_price": None,
        "market_reference_note": "已達正式估價最低樣本門檻，市場單價可納入正式估價。",
        "comparable_grade_summary": grade_summary,
    }


# ============================================================
# 儲存 CSV
# ============================================================

def save_results(
    rows
):

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=OUTPUT_FIELDS
        )

        writer.writeheader()

        normalized_rows = []
        for row in rows:
            normalized_rows.append({
                field: row.get(field)
                for field in OUTPUT_FIELDS
            })

        writer.writerows(normalized_rows)


# ============================================================
# 主程式
# ============================================================

def main():

    print(
        "=========================================="
    )

    print(
        "第35階段：房仲實戰價格決策引擎 V6.1.2"
    )

    print(
        "=========================================="
    )

    # --------------------------------------------------------
    # 讀取資料
    # --------------------------------------------------------

    listings = load_listings()

    transactions = load_transactions()

    print(
        f"在售物件：{len(listings)} 筆"
    )

    print(
        f"有效成交資料：{len(transactions)} 筆"
    )

    # --------------------------------------------------------
    # 執行
    # --------------------------------------------------------

    results = []

    for listing in listings:

        result = decision_for_listing(
            listing,
            transactions
        )

        results.append(
            result
        )

        print(
            f"{listing['listing_id']} | "
            f"{listing['location']} | "
            f"可比 {result['comparable_count']} 筆 | "
            f"{result.get('comparable_grade_summary', '')} | "
            f"信心 {result.get('confidence', '低')} | "
            f"{result['price_grade']}"
        )

    # --------------------------------------------------------
    # 儲存
    # --------------------------------------------------------

    save_results(
        results
    )

    print(
        f"已輸出：{OUTPUT_FILE}"
    )

    print(
        "第35階段完成：V6.1.2 正式價格／內部參考價格分離＋正式樣本判斷修正。"
    )


# ============================================================
# 執行
# ============================================================

if __name__ == "__main__":
    main()
