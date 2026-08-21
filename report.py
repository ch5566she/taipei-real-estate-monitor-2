# -*- coding: utf-8 -*-

"""
第18階段：完整房市專業報告＋房仲開發作戰儀表板（整合版）

整合：
- 舊版第12階段：房市異常警報＋房仲開發名單
- 舊版第14階段：市場機會雷達＋房仲開發行動
- 舊版第15階段：每日房仲開發 Top 10
- 舊版第16階段：個別成交個案開發雷達 Top 10
- 舊版第17階段：目前在售物件開發雷達 Top 10
- 3／6／12月趨勢＋價格帶分析＋最活躍路段
- 現行 V6.2 房仲實戰價格決策
- 現行 V6.3／第20階段 在售物件 × 實價成交比價
"""

import csv
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from statistics import mean, median

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "data", "taipei_transactions.csv")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
LISTING_COMPARISON_FILE = os.path.join(BASE_DIR, "data", "listing_comparison.json")
PRICING_DECISIONS_FILE = os.path.join(BASE_DIR, "data", "pricing_decisions.csv")

LISTING_FILES = [
    os.path.join(BASE_DIR, "data", "current_listings.csv"),
    os.path.join(BASE_DIR, "data", "on_sale.csv"),
    os.path.join(BASE_DIR, "data", "onsale.csv"),
    os.path.join(BASE_DIR, "data", "for_sale.csv"),
    os.path.join(BASE_DIR, "data", "591_listings.csv"),
    os.path.join(BASE_DIR, "data", "market_listings.csv"),
    os.path.join(BASE_DIR, "data", "listings.csv"),
]

TARGET_DISTRICTS = ["士林區", "北投區"]

PRICE_BANDS = [
    ("50萬以下", None, 50),
    ("50–70萬", 50, 70),
    ("70–90萬", 70, 90),
    ("90–110萬", 90, 110),
    ("110萬以上", 110, None),
]

def to_float(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = (
        text
        .replace(",", "")
        .replace("，", "")
    )

    try:
        return float(text)

    except (ValueError, TypeError):
        return None

def parse_date(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # 去除日期後面的時間
    text = text.split(" ")[0]

    # ========================================================
    # 純數字日期
    #
    # 民國：
    # 1150528 → 2026-05-28
    #
    # 西元：
    # 20260528 → 2026-05-28
    # ========================================================

    compact = re.sub(
        r"[^0-9]",
        "",
        text
    )

    # --------------------------------------------------------
    # 民國 7 碼
    # 例如：1150528
    # --------------------------------------------------------

    if re.fullmatch(
        r"\d{7}",
        compact
    ):

        year = (
            int(compact[:3])
            + 1911
        )

        month = int(
            compact[3:5]
        )

        day = int(
            compact[5:7]
        )

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            pass

    # --------------------------------------------------------
    # 西元 8 碼
    # 例如：20260528
    # --------------------------------------------------------

    if re.fullmatch(
        r"\d{8}",
        compact
    ):

        year = int(
            compact[:4]
        )

        month = int(
            compact[4:6]
        )

        day = int(
            compact[6:8]
        )

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            pass

    # ========================================================
    # 一般日期格式
    # ========================================================

    text = (
        text
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )

    # ========================================================
    # 民國日期
    #
    # 例如：
    # 115-05-28
    # ========================================================

    match = re.match(
        r"^(\d{2,3})-(\d{1,2})-(\d{1,2})$",
        text
    )

    if match:

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        day = int(
            match.group(3)
        )

        if year < 1911:

            year += 1911

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            return None

    # ========================================================
    # 西元日期
    #
    # 例如：
    # 2026-05-28
    # ========================================================

    match = re.match(
        r"^(\d{4})-(\d{1,2})-(\d{1,2})$",
        text
    )

    if match:

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        day = int(
            match.group(3)
        )

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            return None

    return None

def get_transaction_date(row):

    fields = [
        "sdate",
        "fdate",
        "transaction_date",
        "trade_date",
        "date",
    ]

    for field in fields:

        parsed = parse_date(
            row.get(field)
        )

        if parsed:
            return parsed

    return None

def extract_route(location):

    if not location:
        return "未知路段"

    text = str(location).strip()

    # --------------------------------------------------------
    # 移除行政區前綴
    #
    # 例如：
    # 台北市士林區天母西路50號
    # ↓
    # 天母西路50號
    #
    # 台北市北投區中山北路七段20號
    # ↓
    # 中山北路七段20號
    # --------------------------------------------------------

    text = re.sub(
        r"^.*?(?:士林區|北投區)",
        "",
        text
    )

    # --------------------------------------------------------
    # 找出道路名稱
    #
    # 可以辨識：
    # 天母西路
    # 德行東路
    # 中山北路六段
    # 承德路七段
    # 克強路
    # 美崙街
    # --------------------------------------------------------

    pattern = (
        r"[\u4e00-\u9fff]{2,10}"
        r"(?:路|街|大道)"
        r"(?:[0-9一二三四五六七八九十百]+段)?"
    )

    match = re.search(
        pattern,
        text
    )

    if match:
        return match.group(0)

    return "其他"

def load_records():

    if not os.path.exists(INPUT_FILE):

        print(
            f"找不到資料檔案：{INPUT_FILE}"
        )

        return []

    records = []

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            district = str(
                row.get("district", "")
            ).strip()

            if district not in TARGET_DISTRICTS:
                continue

            case_type = str(
                row.get("case_t", "")
            ).strip()

            if case_type != "買賣":
                continue

            unit_price = to_float(
                row.get("uprice")
            )

            total_price = to_float(
                row.get("price")
            )

            if total_price is None:

                total_price = to_float(
                    row.get("tprice")
                )

            area = to_float(
                row.get("farea")
            )

            if (
                unit_price is None
                or unit_price <= 0
                or total_price is None
                or total_price <= 0
                or area is None
                or area <= 0
            ):
                continue

            records.append({

                "row": row,

                "district": district,

                "unit_price": unit_price,

                "total_price": total_price,

                "area": area,

                "route": extract_route(
                    row.get("location", "")
                ),

                "date": get_transaction_date(
                    row
                ),

            })

    return records

def percentile(values, percent):

    if not values:
        return None

    data = sorted(values)

    if len(data) == 1:
        return data[0]

    position = (
        (len(data) - 1)
        * percent
    )

    lower = int(position)

    upper = lower + 1

    if upper >= len(data):

        return data[lower]

    weight = position - lower

    return (
        data[lower]
        * (1 - weight)
        +
        data[upper]
        * weight
    )

def analyze_district(items):

    prices = [
        item["unit_price"]
        for item in items
    ]

    totals = [
        item["total_price"]
        for item in items
    ]

    areas = [
        item["area"]
        for item in items
    ]

    q1 = percentile(
        prices,
        0.25
    )

    q3 = percentile(
        prices,
        0.75
    )

    if q1 is not None and q3 is not None:

        iqr = q3 - q1

        lower = q1 - 1.5 * iqr

        upper = q3 + 1.5 * iqr

    else:

        lower = None
        upper = None

    normal = []

    abnormal = []

    for item in items:

        if (
            lower is not None
            and upper is not None
            and (
                item["unit_price"] < lower
                or
                item["unit_price"] > upper
            )
        ):

            abnormal.append(item)

        else:

            normal.append(item)

    normal_prices = [
        item["unit_price"]
        for item in normal
    ]

    return {

        "count": len(items),

        "average_price":
            mean(prices),

        "median_price":
            median(prices),

        "max_price":
            max(prices),

        "min_price":
            min(prices),

        "average_total":
            mean(totals),

        "average_area":
            mean(areas),

        "normal_average":
            mean(normal_prices)
            if normal_prices
            else None,

        "abnormal_count":
            len(abnormal),

        "q1": q1,

        "q3": q3,

        "iqr_lower": lower,

        "iqr_upper": upper,

    }

def monthly_trend(items):

    groups = {}

    for item in items:

        date_value = item["date"]

        if not date_value:
            continue

        year, month, day = date_value

        key = (
            year,
            month
        )

        if key not in groups:

            groups[key] = []

        groups[key].append(
            item["unit_price"]
        )

    months = sorted(
        groups.keys()
    )

    result = []

    previous = None

    for year, month in months:

        prices = groups[
            (year, month)
        ]

        average_price = mean(
            prices
        )

        change = None

        if (
            previous is not None
            and previous != 0
        ):

            change = (
                (
                    average_price
                    - previous
                )
                / previous
                * 100
            )

        result.append({

            "month":
                f"{year:04d}-{month:02d}",

            "count":
                len(prices),

            "average":
                average_price,

            "median":
                median(prices),

            "change":
                change,

        })

        previous = average_price

    return result

def determine_trend(months):

    # ========================================================
    # 第10階段：
    # 改用「最近3個月」判斷市場方向
    # 避免拿多年以前的價格直接與最新月份比較
    # ========================================================

    if len(months) < 2:
        return {
            "direction": "資料不足",
            "change": None,
            "confidence": "低",
            "period": "資料不足",
            "latest_count": 0,
            "window_count": 0,
            "warning": "有效月份不足，無法判斷近期趨勢。",
        }

    # 最近3個月
    recent = months[-3:]

    latest = recent[-1]

    latest_average = latest["average"]
    latest_count = latest["count"]

    # 最近3個月交易量
    window_count = sum(
        item["count"]
        for item in recent
    )

    # ========================================================
    # 前期加權平均
    #
    # 例如：
    # 5月 16筆
    # 6月 4筆
    #
    # 會按照交易筆數加權
    # 避免單一小樣本月份影響太大
    # ========================================================

    previous_months = recent[:-1]

    previous_total_count = sum(
        item["count"]
        for item in previous_months
    )

    if previous_total_count <= 0:
        return {
            "direction": "資料不足",
            "change": None,
            "confidence": "低",
            "period": "最近3個月",
            "latest_count": latest_count,
            "window_count": window_count,
            "warning": "前期交易樣本不足。",
        }

    previous_weighted_average = (
        sum(
            item["average"] * item["count"]
            for item in previous_months
        )
        / previous_total_count
    )

    if previous_weighted_average == 0:
        return {
            "direction": "資料不足",
            "change": None,
            "confidence": "低",
            "period": "最近3個月",
            "latest_count": latest_count,
            "window_count": window_count,
            "warning": "前期價格資料不足。",
        }

    # ========================================================
    # 最近價格變化
    # ========================================================

    change = (
        (
            latest_average
            - previous_weighted_average
        )
        / previous_weighted_average
        * 100
    )

    # ========================================================
    # 趨勢方向
    # ========================================================

    if change >= 3:
        direction = "上升"

    elif change <= -3:
        direction = "下降"

    else:
        direction = "盤整"

    # ========================================================
    # 樣本可信度
    # ========================================================

    if latest_count >= 10 and window_count >= 30:

        confidence = "高"

    elif latest_count >= 5 and window_count >= 15:

        confidence = "中"

    else:

        confidence = "低"

    # ========================================================
    # 小樣本警告
    # ========================================================

    if latest_count < 5:

        warning = (
            f"最近月份僅 {latest_count} 筆交易，"
            "近期趨勢僅供參考，"
            "不宜直接解讀為整體房價走勢。"
        )

    elif latest_count < 10:

        warning = (
            f"最近月份 {latest_count} 筆交易，"
            "樣本量中等，建議搭配路段與住宅類型觀察。"
        )

    else:

        warning = (
            "最近月份樣本量相對充足，"
            "可作為近期市場方向參考。"
        )

    return {

        "direction": direction,

        "change": change,

        "confidence": confidence,

        "period": "最近3個月",

        "latest_count": latest_count,

        "window_count": window_count,

        "warning": warning,

    }

def route_analysis(items):

    groups = {}

    for item in items:

        route = item["route"]

        if route not in groups:

            groups[route] = []

        groups[route].append(
            item
        )

    result = []

    for route, group in groups.items():

        if len(group) < 2:

            continue

        prices = [
            item["unit_price"]
            for item in group
        ]

        average_price = mean(
            prices
        )

        heat = (
            len(group)
            * average_price
        )

        result.append({

            "route": route,

            "count": len(group),

            "average":
                average_price,

            "median":
                median(prices),

            "heat":
                heat,

        })

    result.sort(
        key=lambda x: x["heat"],
        reverse=True
    )

    return result

def route_monitor_analysis(items, district_stats):
    """
    路段級異常監控：
    1. 最新月份價格變化
    2. 最新月份交易量變化
    3. 路段平均價與行政區中位數的差距
    4. 房仲開發分數

    注意：
    - 僅使用實際有交易的月份。
    - 至少需要兩個月份才計算路段價格變化。
    - 樣本不足時不產生強烈的異常判斷。
    """
    groups = {}

    for item in items:
        route = item.get("route") or "未知路段"
        date_value = item.get("date")
        if not date_value:
            continue

        groups.setdefault(route, []).append(item)

    district_median = district_stats.get("median_price")

    district_dates = [
        item.get("date")
        for item in items
        if item.get("date")
    ]
    district_latest_key = (
        max((d[0], d[1]) for d in district_dates)
        if district_dates
        else None
    )

    result = []

    for route, group in groups.items():
        if len(group) < 2:
            continue

        month_groups = {}

        for item in group:
            date_value = item.get("date")
            if not date_value:
                continue

            year, month, _ = date_value
            key = (year, month)

            month_groups.setdefault(key, []).append(
                item.get("unit_price")
            )

        month_rows = []
        for (year, month), prices in sorted(month_groups.items()):
            prices = [
                float(p) for p in prices
                if p is not None
            ]
            if not prices:
                continue

            month_rows.append({
                "month": f"{year:04d}-{month:02d}",
                "count": len(prices),
                "average": mean(prices),
            })

        latest = month_rows[-1] if month_rows else None
        previous = month_rows[-2] if len(month_rows) >= 2 else None

        price_change = None
        if latest and previous and previous["average"]:
            price_change = (
                (latest["average"] - previous["average"])
                / previous["average"]
                * 100
            )

        volume_change = None
        if latest and previous and previous["count"]:
            volume_change = (
                (latest["count"] - previous["count"])
                / previous["count"]
                * 100
            )

        route_age_months = None
        if latest and district_latest_key:
            try:
                route_year, route_month = (
                    int(latest["month"][:4]),
                    int(latest["month"][5:7])
                )
                district_year, district_month = district_latest_key
                route_age_months = (
                    (district_year - route_year) * 12
                    + (district_month - route_month)
                )
            except (TypeError, ValueError):
                route_age_months = None

        average_price = mean(
            float(item["unit_price"])
            for item in group
            if item.get("unit_price") is not None
        )

        price_gap = None
        if district_median:
            price_gap = (
                (average_price - district_median)
                / district_median
                * 100
            )

        # 開發分數（100分）：
        # 交易量 30 + 熱度/價格 20 + 最新交易量 20
        # + 資料新鮮度 20 + 異常訊號 10
        count_score = min(len(group) / 10, 1.0) * 30

        heat_score = min(
            (len(group) * average_price) / 1200,
            1.0
        ) * 20

        latest_score = min(
            (latest["count"] if latest else 0) / 5,
            1.0
        ) * 20

        if route_age_months is None:
            recency_score = 0
        elif route_age_months <= 1:
            recency_score = 20
        elif route_age_months <= 3:
            recency_score = 16
        elif route_age_months <= 6:
            recency_score = 11
        elif route_age_months <= 12:
            recency_score = 6
        else:
            recency_score = 0

        signal_score = 0
        if price_change is not None and price_change <= -10:
            signal_score += 10
        elif price_change is not None and price_change >= 10:
            signal_score += 7

        development_score = round(
            count_score
            + heat_score
            + latest_score
            + recency_score
            + signal_score,
            1
        )

        result.append({
            "route": route,
            "count": len(group),
            "average": average_price,
            "latest_month": latest["month"] if latest else None,
            "latest_count": latest["count"] if latest else 0,
            "latest_average": latest["average"] if latest else None,
            "previous_month": previous["month"] if previous else None,
            "previous_count": previous["count"] if previous else 0,
            "previous_average": previous["average"] if previous else None,
            "price_change": price_change,
            "volume_change": volume_change,
            "route_age_months": route_age_months,
            "price_gap_vs_district_median": price_gap,
            "development_score": development_score,
        })

    result.sort(
        key=lambda x: x["development_score"],
        reverse=True
    )

    return result

def _record_label(item):
    row = item.get("row", {}) or {}
    build_type = str(row.get("buitype") or "").strip()
    case_f = str(row.get("case_f") or "").strip()
    elevator = str(row.get("elevator") or "").strip()
    area = item.get("area")
    area_text = f"{area:.1f}坪" if area is not None else "坪數未知"
    parts = [x for x in [build_type, case_f, elevator, area_text] if x]
    return "／".join(parts[:4])

def _first_value(row, names):
    """從多種可能欄位名稱取第一個非空值。"""
    row = row or {}
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return value
    return None

def _listing_is_active(row):
    """若來源提供狀態欄位，盡量排除已售／下架；沒有狀態則視為可用資料。"""
    status = _first_value(row, [
        "status", "listing_status", "sale_status", "物件狀態", "狀態"
    ])
    if status is None:
        return True
    text = str(status).strip().lower()
    blocked = ["已售", "售出", "下架", "撤件", "出租", "租賃", "sold", "closed", "off"]
    return not any(x in text for x in blocked)

def load_listings():
    """讀取可用的在售 CSV；找不到檔案時回傳空集合，不製造假案源。"""
    selected = None
    for path in LISTING_FILES:
        if os.path.exists(path):
            selected = path
            break

    if not selected:
        print("第17階段：尚未找到在售物件 CSV，將以『未接入』狀態產生報告。")
        return [], None

    listings = []
    try:
        with open(selected, "r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                district = str(_first_value(row, [
                    "district", "行政區", "區域", "area_district"
                ]) or "").strip()
                if district not in TARGET_DISTRICTS:
                    continue

                if not _listing_is_active(row):
                    continue

                case_type = _first_value(row, ["case_t", "transaction_type", "type", "物件類型", "交易類型"])
                if case_type and any(x in str(case_type) for x in ["租", "出租", "租賃"]):
                    continue

                location = str(_first_value(row, [
                    "location", "address", "addr", "address_full", "地址", "地點", "路段"
                ]) or "").strip()
                route = extract_route(location)
                if route in ("其他", "未知路段"):
                    route_candidate = str(_first_value(row, ["route", "road", "street", "路段", "道路"]) or "").strip()
                    if route_candidate:
                        route = route_candidate

                total_price = to_float(_first_value(row, [
                    "asking_price", "total_price", "price", "tprice", "總價", "開價", "售價"
                ]))
                area = to_float(_first_value(row, [
                    "area", "building_area", "farea", "坪數", "建物坪數", "權狀坪數", "主建物坪數"
                ]))
                unit_price = to_float(_first_value(row, [
                    "asking_unit_price", "unit_price", "uprice", "單價", "每坪單價", "開價單價"
                ]))

                if unit_price is None and total_price is not None and area and area > 0:
                    unit_price = total_price / area

                if total_price is None and unit_price is not None and area and area > 0:
                    total_price = unit_price * area

                if unit_price is None or unit_price <= 0 or area is None or area <= 0:
                    continue

                listing_date = _first_value(row, [
                    "listing_date", "publish_date", "date", "created_at", "上架日期", "更新日期"
                ])
                title = str(_first_value(row, [
                    "title", "name", "property_name", "build_name", "物件名稱", "標題"
                ]) or "").strip()
                url = str(_first_value(row, [
                    "url", "link", "property_url", "物件網址", "網址"
                ]) or "").strip()
                build_type = str(_first_value(row, [
                    "buitype", "building_type", "type_name", "建物型態", "物件型態"
                ]) or "").strip()
                rooms = str(_first_value(row, [
                    "rooms", "room", "bedrooms", "格局", "房數"
                ]) or "").strip()
                age = to_float(_first_value(row, [
                    "age", "building_age", "屋齡"
                ]))

                listings.append({
                    "row": row,
                    "district": district,
                    "route": route,
                    "location": location,
                    "title": title,
                    "url": url,
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "area": area,
                    "listing_date": str(listing_date or "").strip(),
                    "build_type": build_type,
                    "rooms": rooms,
                    "age": age,
                })
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        print(f"第17階段：讀取在售物件資料失敗：{exc}")
        return [], selected

    print(f"第17階段：讀取在售物件 {len(listings):,} 筆，來源：{selected}")
    return listings, selected

def build_stage16_property_radar(records, report):
    """
    以「已成交個案」建立個別物件級開發線索。

    重要限制：目前資料來源是實價成交資料，不是在售物件資料，
    因此本階段不宣稱知道屋主、目前開價或物件是否仍在市場上。
    用途是找出「值得沿著該成交個案去找同路段／同類型屋主」的線索。
    """
    route_stats = {}
    route_scores = {}
    for district, data in report.get("districts", {}).items():
        for route in data.get("route_monitor", []) or []:
            key = (district, route.get("route") or "未知路段")
            route_stats[key] = route
            route_scores[key] = float(route.get("development_score") or 0)

    # 先建立每個路段的成交單價集合，計算個案相對於同路段中位數的偏離。
    route_prices = {}
    for item in records:
        key = (item.get("district"), item.get("route") or "未知路段")
        route_prices.setdefault(key, []).append(float(item.get("unit_price") or 0))

    dated = [x for x in records if x.get("date")]
    latest_key = max((x["date"][0], x["date"][1], x["date"][2]) for x in dated) if dated else None

    candidates = []
    for item in records:
        date_value = item.get("date")
        if not date_value:
            continue

        district = item.get("district") or ""
        route = item.get("route") or "未知路段"
        unit_price = float(item.get("unit_price") or 0)
        area = item.get("area")
        if unit_price <= 0:
            continue

        key = (district, route)
        peer_prices = route_prices.get(key, [])
        peer_median = median(peer_prices) if peer_prices else None
        peer_avg = mean(peer_prices) if peer_prices else None
        district_median = None
        district_data = report.get("districts", {}).get(district, {})
        if district_data:
            district_median = to_float(district_data.get("stats", {}).get("median_price"))

        peer_gap = None
        if peer_median:
            peer_gap = (unit_price - peer_median) / peer_median * 100

        district_gap = None
        if district_median:
            district_gap = (unit_price - district_median) / district_median * 100

        if latest_key:
            months_old = (latest_key[0] - date_value[0]) * 12 + (latest_key[1] - date_value[1])
        else:
            months_old = 99

        recency_score = 30 if months_old <= 1 else 24 if months_old <= 3 else 18 if months_old <= 6 else 10 if months_old <= 12 else 3
        route_score = min(route_scores.get(key, 0) / 60 * 20, 20)

        deviation_score = 0
        if peer_gap is not None:
            abs_gap = abs(peer_gap)
            if abs_gap >= 25:
                deviation_score = 25
            elif abs_gap >= 15:
                deviation_score = 21
            elif abs_gap >= 10:
                deviation_score = 17
            elif abs_gap >= 5:
                deviation_score = 12
            else:
                deviation_score = 7

        district_score = 0
        if district_gap is not None:
            if district_gap <= -20 or district_gap >= 20:
                district_score = 15
            elif abs(district_gap) >= 10:
                district_score = 11
            else:
                district_score = 6

        completeness_score = 10 if area and item.get("total_price") else 5
        score = round(min(100, recency_score + route_score + deviation_score + district_score + completeness_score), 1)

        reasons = []
        actions = []
        if months_old <= 3:
            reasons.append("近3個月成交")
            actions.append("優先查同路段目前在售")
        elif months_old <= 12:
            reasons.append("近12個月內成交")
        if route_scores.get(key, 0) >= 50:
            reasons.append(f"路段開發分數{route_scores[key]:.1f}")
            actions.append("沿成交路段建立同類屋主名單")
        if peer_gap is not None and abs(peer_gap) >= 15:
            reasons.append(f"與路段中位價偏離{peer_gap:+.1f}%")
            actions.append("檢查同類型產品價格差異")
        if district_gap is not None and abs(district_gap) >= 20:
            reasons.append(f"與行政區中位價偏離{district_gap:+.1f}%")
            actions.append("確認屋齡、樓層、格局與車位差異")
        if not reasons:
            reasons.append("具備可追蹤成交紀錄")
        if not actions:
            actions.append("列入同類物件開發追蹤")

        priority = "A｜優先開發" if score >= 75 else "B｜本週追蹤" if score >= 60 else "C｜持續觀察"
        row = item.get("row", {}) or {}
        location = str(row.get("location") or "").strip()
        transaction_id = str(row.get("_id") or "").strip()
        candidates.append({
            "district": district,
            "route": route,
            "transaction_id": transaction_id,
            "transaction_date": f"{date_value[0]:04d}-{date_value[1]:02d}-{date_value[2]:02d}",
            "location": location,
            "unit_price": unit_price,
            "total_price": item.get("total_price"),
            "area": area,
            "product": _record_label(item),
            "peer_median": peer_median,
            "district_median": district_median,
            "peer_gap": peer_gap,
            "district_gap": district_gap,
            "route_score": route_scores.get(key, 0),
            "score": score,
            "priority": priority,
            "reasons": reasons[:4],
            "actions": actions[:3],
            "note": "成交個案開發線索；不代表目前仍在售，也不代表可識別屋主。",
        })

    candidates.sort(key=lambda x: (x["score"], x["transaction_date"]), reverse=True)
    for idx, item in enumerate(candidates[:10], 1):
        item["rank"] = idx

    return {
        "generated_for": "個別成交個案開發雷達 Top 10",
        "top10": candidates[:10],
        "note": "目前以實價成交個案作為同路段／同類型屋主開發線索；尚未接入591等在售物件資料，因此不判定物件目前是否在售。",
    }

def build_stage16_property_board(report):
    data = report.get("property_radar") or {}
    top10 = data.get("top10", []) or []
    if not top10:
        return """
        <section class="stage16">
            <h2>🏠 第16階段｜個別成交個案開發雷達</h2>
            <div class="analysis-note">目前沒有足夠成交個案資料建立個別開發線索。</div>
        </section>
        """

    rows = []
    for x in top10:
        peer = "—" if x.get("peer_median") is None else f"{x['peer_median']:.2f}"
        gap = "—" if x.get("peer_gap") is None else f"{x['peer_gap']:+.1f}%"
        total = "—" if x.get("total_price") is None else f"{x['total_price']:,.0f}"
        reasons = "；".join(x.get("reasons", [])[:2])
        rows.append(f"""
        <tr>
            <td><strong>#{x['rank']}</strong></td>
            <td>{html_escape(x['district'])}</td>
            <td>{html_escape(x['route'])}</td>
            <td>{html_escape(x['transaction_date'])}</td>
            <td>{x['unit_price']:.2f}</td>
            <td>{peer}</td>
            <td>{gap}</td>
            <td><strong>{x['score']:.1f}</strong><br><small>{html_escape(x['priority'])}</small></td>
            <td>{html_escape(reasons)}</td>
        </tr>
        """)

    focus = top10[0]
    focus_reason = "；".join(focus.get("reasons", [])[:3])
    focus_action = "；".join(focus.get("actions", [])[:3])
    return f"""
    <section class="stage16">
        <h2>🏠 第16階段｜個別成交個案開發雷達 Top 10</h2>
        <div class="stage16-focus">
            <strong>🎯 今日第一優先線索：</strong>
            {html_escape(focus['district'])} × {html_escape(focus['route'])}｜
            {html_escape(focus['transaction_date'])}｜
            開發分數 <strong>{focus['score']:.1f}</strong>｜{html_escape(focus['priority'])}<br>
            <strong>為什麼：</strong>{html_escape(focus_reason)}<br>
            <strong>建議：</strong>{html_escape(focus_action)}
        </div>
        <table>
            <tr>
                <th>排名</th><th>行政區</th><th>路段</th><th>成交日期</th>
                <th>成交單價</th><th>路段中位價</th><th>價格偏離</th>
                <th>開發分數</th><th>開發訊號</th>
            </tr>
            {''.join(rows)}
        </table>
        <div class="stage16-note">
            ⚠️ 本階段是「成交個案→同類屋主開發線索」，不是目前在售物件名單，也不是屋主身份判定。
            若要做到真正的「目前哪一間房子最值得開發」，下一步必須接入在售物件資料，再比對成交行情與目前開價。
        </div>
    </section>
    """

def build_stage17_listing_radar(listings, records, report, source_path=None):
    """目前在售物件與近期成交／路段熱度交叉比對。"""
    if not listings:
        return {
            "source": source_path,
            "count": 0,
            "connected": False,
            "top10": [],
            "note": "尚未接入目前在售物件資料；目前報告不判定任何個別在售物件。",
        }

    route_prices = {}
    route_heat = {}
    route_count = {}
    for item in records:
        key = (item.get("district"), item.get("route") or "未知路段")
        route_prices.setdefault(key, []).append(float(item.get("unit_price") or 0))
        route_count[key] = route_count.get(key, 0) + 1

    # 使用目前報告已算好的路段熱度／開發分數；若沒有則退回成交筆數。
    for district, data in report.get("districts", {}).items():
        for route in data.get("route_monitor", []) or []:
            key = (district, route.get("route") or "未知路段")
            route_heat[key] = float(route.get("heat") or 0)

    district_medians = {
        district: to_float(data.get("stats", {}).get("median_price"))
        for district, data in report.get("districts", {}).items()
    }

    max_heat = max(route_heat.values()) if route_heat else 0
    candidates = []
    for item in listings:
        key = (item.get("district"), item.get("route") or "未知路段")
        prices = [p for p in route_prices.get(key, []) if p > 0]
        route_median = median(prices) if prices else None
        district_median = district_medians.get(item.get("district"))
        ask = float(item.get("unit_price") or 0)

        route_gap = None if not route_median else (ask - route_median) / route_median * 100
        district_gap = None if not district_median else (ask - district_median) / district_median * 100

        # 40分價格機會：越接近或低於成交中位數越高；明顯高於市場則降分。
        if route_gap is None:
            price_score = 12
        elif route_gap <= -20:
            price_score = 40
        elif route_gap <= -10:
            price_score = 34
        elif route_gap <= -5:
            price_score = 28
        elif route_gap <= 5:
            price_score = 22
        elif route_gap <= 10:
            price_score = 15
        elif route_gap <= 20:
            price_score = 8
        else:
            price_score = 3

        # 25分路段熱度。
        heat = route_heat.get(key, 0)
        if max_heat > 0:
            heat_score = min(25, heat / max_heat * 25)
        else:
            heat_score = min(25, route_count.get(key, 0) * 3)

        # 20分資料完整度／可操作性。
        completeness = 0
        if item.get("location") or item.get("route") not in ("其他", "未知路段"):
            completeness += 5
        if item.get("area"):
            completeness += 5
        if item.get("total_price"):
            completeness += 4
        if item.get("title"):
            completeness += 3
        if item.get("url"):
            completeness += 3

        # 15分成交樣本量與同路段可比性。
        sample = route_count.get(key, 0)
        sample_score = min(15, sample * 2.5)

        score = round(min(100, price_score + heat_score + completeness + sample_score), 1)
        priority = "A｜優先研究" if score >= 75 else "B｜本週追蹤" if score >= 60 else "C｜持續觀察"

        reasons = []
        actions = []
        if route_gap is not None and route_gap <= -10:
            reasons.append(f"開價低於同路段成交中位價{abs(route_gap):.1f}%")
            actions.append("優先檢查同類型成交條件與產品差異")
        elif route_gap is not None and route_gap >= 15:
            reasons.append(f"開價高於同路段成交中位價{route_gap:.1f}%")
            actions.append("列為高開價競品，觀察議價與銷售週期")
        if route_count.get(key, 0) >= 4:
            reasons.append(f"同路段近期成交樣本{route_count[key]}筆")
            actions.append("建立同路段價格帶與競品清單")
        if heat >= max_heat * 0.5 and max_heat > 0:
            reasons.append("所在路段屬高熱度路段")
            actions.append("列入每日重點追蹤")
        if district_gap is not None and abs(district_gap) >= 15:
            reasons.append(f"與行政區中位價偏離{district_gap:+.1f}%")
            actions.append("再用屋齡、樓層、格局、車位修正比較")
        if not reasons:
            reasons.append("已有在售資料且可與成交行情交叉比對")
        if not actions:
            actions.append("持續追蹤價格與成交變化")

        candidates.append({
            "district": item.get("district"),
            "route": item.get("route"),
            "location": item.get("location"),
            "title": item.get("title"),
            "url": item.get("url"),
            "unit_price": ask,
            "total_price": item.get("total_price"),
            "area": item.get("area"),
            "build_type": item.get("build_type"),
            "rooms": item.get("rooms"),
            "age": item.get("age"),
            "route_median": route_median,
            "district_median": district_median,
            "route_gap": route_gap,
            "district_gap": district_gap,
            "route_heat": heat,
            "route_transaction_count": sample,
            "score": score,
            "priority": priority,
            "reasons": reasons[:4],
            "actions": actions[:3],
        })

    candidates.sort(key=lambda x: (x["score"], -(abs(x["route_gap"]) if x.get("route_gap") is not None else 999)), reverse=True)
    for idx, item in enumerate(candidates[:10], 1):
        item["rank"] = idx

    return {
        "source": source_path,
        "count": len(listings),
        "connected": True,
        "top10": candidates[:10],
        "note": "在售物件多數屬市場競品資料；除非來源明確提供屋主資訊，系統不判定屋主身份。價格比較亦非正式估價。",
    }

def build_stage17_listing_board(report):
    data = report.get("listing_radar") or {}
    top10 = data.get("top10", []) or []
    count = int(data.get("count") or 0)
    source = data.get("source") or "尚未找到在售 CSV"
    if not data.get("connected"):
        return f"""
        <section class="stage17">
            <h2>🔥 第17階段｜今日房仲在售物件開發雷達</h2>
            <div class="stage17-focus">
                <strong>目前尚未接入在售物件資料。</strong><br>
                系統已保留完整介面；下一次只要把在售資料放入指定 CSV，便會自動產生「在售開價 × 成交中位價 × 路段熱度 × 開發分數 Top 10」。
            </div>
            <div class="stage17-note">
                預設資料位置：data/current_listings.csv、data/on_sale.csv、data/591_listings.csv 或 data/listings.csv。<br>
                ⚠️ 沒有在售資料時，本階段不捏造任何物件、不假設目前在售，也不判定屋主身份。
            </div>
        </section>
        """

    rows = []
    for x in top10:
        route_median = "—" if x.get("route_median") is None else f"{x['route_median']:.2f}"
        gap = "—" if x.get("route_gap") is None else f"{x['route_gap']:+.1f}%"
        total = "—" if x.get("total_price") is None else f"{x['total_price']:,.0f}"
        area = "—" if x.get("area") is None else f"{x['area']:.1f}"
        reason = "；".join(x.get("reasons", [])[:2])
        title = x.get("title") or x.get("location") or x.get("route") or "未命名物件"
        rows.append(f"""
        <tr>
            <td><strong>#{x['rank']}</strong></td>
            <td>{html_escape(x.get('district'))}</td>
            <td>{html_escape(x.get('route'))}<br><small>{html_escape(title)}</small></td>
            <td>{total}</td>
            <td>{area}</td>
            <td>{x['unit_price']:.2f}</td>
            <td>{route_median}</td>
            <td>{gap}</td>
            <td>{x['route_transaction_count']}筆<br>{x['route_heat']:.2f}</td>
            <td><strong>{x['score']:.1f}</strong><br><small>{html_escape(x['priority'])}</small></td>
            <td>{html_escape(reason)}</td>
        </tr>
        """)

    focus = top10[0]
    focus_reason = "；".join(focus.get("reasons", [])[:3])
    focus_action = "；".join(focus.get("actions", [])[:3])
    url_html = ""
    if focus.get("url"):
        url_html = f'<br><a href="{html_escape(focus["url"])}" target="_blank" rel="noopener">查看物件來源</a>'

    return f"""
    <section class="stage17">
        <h2>🔥 第17階段｜今日房仲在售物件開發雷達 Top 10</h2>
        <div class="stage17-summary-grid">
            <div class="stage17-summary-card"><div class="stage17-summary-title">🏠 在售資料</div><strong>{count:,} 筆</strong><small>來源：{html_escape(source)}</small></div>
            <div class="stage17-summary-card"><div class="stage17-summary-title">🎯 第一優先</div><strong>{focus['score']:.1f}</strong><small>{html_escape(focus['district'])}｜{html_escape(focus['route'])}</small></div>
            <div class="stage17-summary-card"><div class="stage17-summary-title">📊 比價基準</div><strong>{'可比' if focus.get('route_median') is not None else '不足'}</strong><small>同路段成交中位價</small></div>
        </div>
        <div class="stage17-focus">
            <strong>🎯 今日第一優先物件：</strong>
            {html_escape(focus.get('district'))} × {html_escape(focus.get('route'))} × {html_escape(focus.get('title') or focus.get('location') or '未命名物件')}<br>
            <strong>開價：</strong>{focus['unit_price']:.2f} 萬／坪；
            <strong>同路段成交中位價：</strong>{'—' if focus.get('route_median') is None else f"{focus['route_median']:.2f} 萬／坪"}；
            <strong>價格偏離：</strong>{'—' if focus.get('route_gap') is None else f"{focus['route_gap']:+.1f}%"}；
            <strong>開發分數：</strong>{focus['score']:.1f}<br>
            <strong>為什麼：</strong>{html_escape(focus_reason)}<br>
            <strong>建議：</strong>{html_escape(focus_action)}{url_html}
        </div>
        <div class="table-scroll">
        <table class="stage17-table">
            <tr>
                <th>排名</th><th>行政區</th><th>路段／物件</th><th>總價</th><th>坪數</th>
                <th>目前開價</th><th>成交中位</th><th>價格偏離</th><th>路段熱度</th><th>開發分數</th><th>開發訊號</th>
            </tr>
            {''.join(rows)}
        </table>
        </div>
        <div class="stage17-note">
            📌 本階段是「目前在售物件的市場機會／競品研究排序」，不是單一物件正式估價，也不是屋主身份判定。<br>
            若資料來源是仲介公開物件，系統會將其視為市場競品；只有來源明確標示屋主資訊時，才可另行處理聯絡資訊。
        </div>
    </section>
    """

def calculate_window_change(months, window):
    """
    計算最近 N 個「有資料月份」的價格變化。
    以第一個月份與最新月份的平均單價比較。
    注意：月份可能不連續，因此標示為「最近N個有資料月份」。
    """
    valid = [
        item for item in (months or [])
        if item.get("average") is not None
    ]

    if len(valid) < 2:
        return None

    recent = valid[-window:] if len(valid) >= window else valid

    first = to_float(recent[0].get("average"))
    latest = to_float(recent[-1].get("average"))

    if first in (None, 0) or latest is None:
        return None

    return (latest - first) / first * 100

def get_recent_month_info(months, window=3):
    """取得最近 N 個有資料月份的摘要。"""
    valid = [
        item for item in (months or [])
        if item.get("average") is not None
    ]

    if not valid:
        return {
            "count": 0,
            "start_month": None,
            "end_month": None,
            "change": None,
            "latest_average": None,
            "latest_count": 0,
        }

    recent = valid[-window:]
    latest = recent[-1]

    return {
        "count": len(recent),
        "start_month": recent[0].get("month"),
        "end_month": latest.get("month"),
        "change": calculate_window_change(valid, window),
        "latest_average": latest.get("average"),
        "latest_count": latest.get("count", 0),
    }

def build_trend_windows(months):
    """
    計算最近 3／6／12 個「有資料月份」的價格變化。
    注意：月份可能不連續，因此明確標示為「有資料月份」。
    """
    result = {}

    for window in (3, 6, 12):
        info = get_recent_month_info(months, window)
        info["window"] = window
        info["label"] = f"近{window}個有資料月份"
        result[str(window)] = info

    return result

def build_price_bands(items):
    """
    依每筆成交單價建立價格帶。
    單價單位沿用本系統的「萬元／坪」。
    """
    total = len(items)
    result = []

    for label, lower, upper in PRICE_BANDS:
        group = []

        for item in items:
            price = to_float(item.get("unit_price"))

            if price is None:
                continue

            if lower is None:
                matched = price < upper
            elif upper is None:
                matched = price >= lower
            else:
                matched = lower <= price < upper

            if matched:
                group.append(item)

        count = len(group)
        share = (count / total * 100) if total else None
        average = (
            mean(item["unit_price"] for item in group)
            if group else None
        )

        result.append({
            "band": label,
            "lower": lower,
            "upper": upper,
            "count": count,
            "share": share,
            "average": average,
        })

    return result

def build_price_band_summary(price_bands):
    """找出交易量最高的價格帶。"""
    valid = [
        item for item in (price_bands or [])
        if item.get("count", 0) > 0
    ]

    if not valid:
        return None

    return max(valid, key=lambda item: item.get("count", 0))

def build_decision_dashboard(report):
    """
    第11階段：房仲實戰決策儀表板。
    所有數字與建議均依當日 report 動態計算。
    """
    districts = report.get("districts", {})
    names = [n for n in TARGET_DISTRICTS if n in districts]

    if not names:
        return """
        <section class="decision-dashboard">
            <h2>🎯 房仲實戰決策儀表板</h2>
            <div class="analysis-note">目前沒有足夠資料產生決策儀表板。</div>
        </section>
        """

    metrics = {}

    for district in names:
        data = districts[district]
        months = data.get("months", [])
        stats = data.get("stats", {})
        trend = data.get("trend", {})

        recent3 = get_recent_month_info(months, 3)
        recent6 = get_recent_month_info(months, 6)
        recent12 = get_recent_month_info(months, 12)
        trend_windows = data.get("trend_windows", {})

        metrics[district] = {
            "count": stats.get("count", 0),
            "average": stats.get("average_price"),
            "median": stats.get("median_price"),
            "trend": trend.get("direction", "資料不足"),
            "trend_change": trend.get("change"),
            "confidence": trend.get("confidence", "低"),
            "recent3": recent3,
            "recent6": recent6,
            "recent12": recent12,
            "trend_windows": trend_windows,
        }

    # --------------------------------------------------------
    # 跨行政區比較
    # --------------------------------------------------------
    volume_rank = sorted(
        names,
        key=lambda n: metrics[n]["count"],
        reverse=True,
    )

    price_rank = sorted(
        names,
        key=lambda n: (
            metrics[n]["average"]
            if metrics[n]["average"] is not None
            else float("-inf")
        ),
        reverse=True,
    )

    recent_change_values = [
        (n, metrics[n]["recent3"]["change"])
        for n in names
        if metrics[n]["recent3"]["change"] is not None
    ]

    if recent_change_values:
        strongest = max(recent_change_values, key=lambda x: x[1])
        weakest = min(recent_change_values, key=lambda x: x[1])
    else:
        strongest = weakest = None

    total_volume = sum(metrics[n]["count"] for n in names)
    volume_text = "；".join(
        f"{n} {metrics[n]['count']:,}筆"
        for n in volume_rank
    )

    if len(names) >= 2:
        a, b = price_rank[0], price_rank[1]
        avga = metrics[a]["average"]
        avgb = metrics[b]["average"]

        if avga is not None and avgb is not None and avgb != 0:
            gap_pct = (avga - avgb) / avgb * 100
            price_gap_text = (
                f"{a}平均單價較{b}高 "
                f"{gap_pct:+.2f}%。"
            )
        else:
            price_gap_text = "兩區平均單價資料不足，暫無法比較。"
    else:
        price_gap_text = "目前只有一個行政區有資料。"

    # --------------------------------------------------------
    # 警示
    # --------------------------------------------------------
    alerts = []

    for district in names:
        m = metrics[district]
        change3 = m["recent3"]["change"]
        latest_count = m["recent3"]["latest_count"]

        if change3 is not None and change3 <= -10:
            alerts.append(
                f"🔴 {district}最近3個有資料月份價格下跌 "
                f"{abs(change3):.2f}%，應提高議價與定價風險注意。"
            )
        elif change3 is not None and change3 >= 10:
            alerts.append(
                f"🟢 {district}最近3個有資料月份價格上升 "
                f"{change3:.2f}%，可留意高需求產品的價格支撐。"
            )

        if latest_count < 3:
            alerts.append(
                f"⚠️ {district}最新月份僅 {latest_count} 筆，"
                "近期價格訊號可信度偏低。"
            )

    if not alerts:
        alerts.append(
            "🟡 目前沒有觸發明顯價格異常警示，仍應搭配路段與產品類型判讀。"
        )

    # --------------------------------------------------------
    # 房仲實戰建議
    # --------------------------------------------------------
    if strongest and strongest[1] >= 5:
        seller_advice = (
            f"{strongest[0]}近期價格相對有支撐，可優先整理近期成交案例，"
            "協助屋主建立合理售價區間。"
        )
    elif weakest and weakest[1] <= -5:
        seller_advice = (
            f"{weakest[0]}近期價格修正較明顯，賣方開價應更貼近實價，"
            "並預留合理議價空間，以降低銷售週期。"
        )
    else:
        seller_advice = (
            "目前兩區沒有形成明顯單邊價格訊號，賣方應採「同路段、"
            "同屋齡、同產品」三項條件比價後定價。"
        )

    if weakest and weakest[1] <= -5:
        buyer_advice = (
            f"買方可優先關注{weakest[0]}近期價格修正的物件，"
            "但要排除低總價、特殊屋況或非主流產品造成的價格偏差。"
        )
    else:
        buyer_advice = (
            "買方宜以近期成交與同路段產品交叉比價，不宜只用行政區平均價判斷單一物件。"
        )

    # 路段開發重點：每區第一名
    route_targets = []
    for district in names:
        routes = districts[district].get("routes", [])
        if routes:
            top = routes[0]
            route_targets.append(
                f"{district}：{top.get('route', '未命名路段')} "
                f"（{top.get('count', 0)}筆／熱度 {money(top.get('heat'))}）"
            )

    route_text = "；".join(route_targets) if route_targets else "目前沒有足夠路段資料。"

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------
    metric_cards = ""

    for district in names:
        m = metrics[district]
        c3 = m["recent3"]["change"]
        c6 = m["recent6"]["change"]
        c12 = m["recent12"]["change"]

        c3_text = "—" if c3 is None else f"{c3:+.2f}%"
        c6_text = "—" if c6 is None else f"{c6:+.2f}%"
        c12_text = "—" if c12 is None else f"{c12:+.2f}%"

        metric_cards += f"""
        <div class="decision-card">
            <div class="decision-card-title">{html_escape(district)}</div>
            <div class="decision-row">
                <span>交易量</span>
                <strong>{m['count']:,} 筆</strong>
            </div>
            <div class="decision-row">
                <span>平均單價</span>
                <strong>{money(m['average'])} 萬／坪</strong>
            </div>
            <div class="decision-row">
                <span>近3個有資料月份</span>
                <strong>{c3_text}</strong>
            </div>
            <div class="decision-row">
                <span>近6個有資料月份</span>
                <strong>{c6_text}</strong>
            </div>
            <div class="decision-row">
                <span>近12個有資料月份</span>
                <strong>{c12_text}</strong>
            </div>
        </div>
        """

    alert_html = "".join(
        f"<li>{html_escape(item)}</li>"
        for item in alerts
    )

    return f"""
    <section class="decision-dashboard">
        <h2>🎯 房仲實戰決策儀表板</h2>

        <div class="decision-summary">
            <div class="decision-summary-card">
                <div class="decision-summary-title">📊 交易量</div>
                <div>{html_escape(volume_text)}</div>
                <small>合計 {total_volume:,} 筆</small>
            </div>

            <div class="decision-summary-card">
                <div class="decision-summary-title">💰 價格差距</div>
                <div>{html_escape(price_gap_text)}</div>
            </div>

            <div class="decision-summary-card">
                <div class="decision-summary-title">🔥 開發路段</div>
                <div>{html_escape(route_text)}</div>
            </div>
        </div>

        <div class="decision-metrics">
            {metric_cards}
        </div>

        <div class="decision-grid">
            <div class="decision-panel seller">
                <h3>🏠 賣方策略</h3>
                <p>{html_escape(seller_advice)}</p>
            </div>

            <div class="decision-panel buyer">
                <h3>🔎 買方策略</h3>
                <p>{html_escape(buyer_advice)}</p>
            </div>

            <div class="decision-panel developer">
                <h3>📞 房仲開發重點</h3>
                <p>
                    優先追蹤交易量高、近期價格有明顯變化的路段，
                    並將同路段成交案例整理成屋主可理解的價格帶。
                    目前重點：{html_escape(route_text)}
                </p>
            </div>
        </div>

        <div class="decision-alerts">
            <h3>🚨 今日市場警示</h3>
            <ul>{alert_html}</ul>
        </div>

        <div class="analysis-note">
            📌 本區塊為資料分析輔助，不代表單一物件的估價；實際委託開發仍應搭配屋齡、
            樓層、格局、管理、車位、路段及個案成交條件。
        </div>
    </section>
    """

def build_market_comparison(report):
    """建立士林／北投比較分析與房仲市場判讀。"""
    districts = report.get("districts", {})
    names = [name for name in TARGET_DISTRICTS if name in districts]

    if not names:
        return """
        <section class="market-analysis">
            <h2>📊 士林／北投市場比較分析</h2>
            <div class="analysis-note">目前沒有足夠的行政區資料可進行比較。</div>
        </section>
        """

    rows = ""
    for district in names:
        data = districts[district]
        stats = data.get("stats", {})
        trend = data.get("trend", {})
        change = trend.get("change")
        change_text = "—" if change is None else f"{change:+.2f}%"
        confidence = trend.get("confidence", "低")
        direction = trend.get("direction", "資料不足")
        rows += f"""
            <tr>
                <td><strong>{html_escape(district)}</strong></td>
                <td>{stats.get('count', 0):,} 筆</td>
                <td>{money(stats.get('average_price'))} 萬／坪</td>
                <td>{money(stats.get('median_price'))} 萬／坪</td>
                <td>{html_escape(direction)}</td>
                <td>{change_text}</td>
                <td>{html_escape(confidence)}</td>
            </tr>
        """

    # 比較基準：交易量、平均單價、近期變化
    volume_name = max(names, key=lambda n: districts[n].get("stats", {}).get("count", 0))
    price_name = max(names, key=lambda n: districts[n].get("stats", {}).get("average_price", float("-inf")))

    changes = []
    for district in names:
        change = districts[district].get("trend", {}).get("change")
        if change is not None:
            changes.append((district, float(change)))

    if changes:
        strongest_up = max(changes, key=lambda x: x[1])
        strongest_down = min(changes, key=lambda x: x[1])
    else:
        strongest_up = strongest_down = None

    volume_text = (
        f"{volume_name}目前有效交易量較高，共 {districts[volume_name]['stats'].get('count', 0):,} 筆。"
    )
    price_text = (
        f"{price_name}目前平均單價較高，約 {money(districts[price_name]['stats'].get('average_price'))} 萬／坪。"
    )

    if strongest_down:
        down_name, down_change = strongest_down
        trend_text = f"近期變化以{down_name}較弱，最近3個月約 {down_change:+.2f}%。"
    elif strongest_up:
        up_name, up_change = strongest_up
        trend_text = f"目前有資料的行政區中，{up_name}近期變化相對較強，約 {up_change:+.2f}%。"
    else:
        trend_text = "目前有效月份不足，無法可靠比較近期價格變化。"

    # 房仲行動建議：完全依照目前資料動態生成
    directions = [
        districts[n].get("trend", {}).get("direction")
        for n in names
    ]

    if all(d == "下降" for d in directions if d not in (None, "資料不足")) and any(d == "下降" for d in directions):
        seller_advice = "近期價格偏弱，賣方定價宜以實價與同類型競品為基準，避免明顯高於市場造成銷售週期拉長。"
        buyer_advice = "買方可優先鎖定價格已修正、但地段與產品條件仍佳的物件，並保留合理議價空間。"
    elif any(d == "上升" for d in directions):
        seller_advice = "有上升訊號的行政區可維持貼近市場的價格策略，並用近期成交案例支撐價格。"
        buyer_advice = "買方宜加快對符合需求且價格合理物件的判斷，避免只看單一高價成交而過度追價。"
    else:
        seller_advice = "市場呈現分化或盤整，賣方應依路段、屋齡、產品型態及近期成交個案精準定價。"
        buyer_advice = "買方可採取比價與議價並行策略，重點觀察同路段、同類型物件的實際成交價格。"

    latest_counts = [districts[n].get("trend", {}).get("latest_count", 0) for n in names]
    low_sample = [n for n in names if districts[n].get("trend", {}).get("confidence") == "低"]
    sample_note = ""
    if low_sample:
        sample_note = (
            "；".join(low_sample) +
            "近期樣本可信度偏低，趨勢應搭配路段與住宅類型交叉判讀。"
        )
    else:
        sample_note = "目前各行政區趨勢可作為方向性參考，但仍應搭配路段與產品條件判讀。"

    route_lines = []
    for district in names:
        routes = districts[district].get("routes", [])
        if routes:
            top = routes[0]
            route_name = html_escape(top.get("route", "未命名路段"))
            route_count = top.get("count", 0)
            route_price = money(top.get("average"))
            route_lines.append(
                f"{html_escape(district)}：{route_name}，{route_count} 筆，平均 {route_price} 萬／坪"
            )

    route_html = "".join(f"<li>{line}</li>" for line in route_lines) or "<li>目前沒有足夠路段資料。</li>"

    return f"""
    <section class="market-analysis">
        <h2>📊 士林／北投市場比較分析</h2>

        <table class="comparison-table">
            <tr>
                <th>行政區</th>
                <th>交易量</th>
                <th>平均單價</th>
                <th>中位數</th>
                <th>近期方向</th>
                <th>近3月變化</th>
                <th>可信度</th>
            </tr>
            {rows}
        </table>

        <div class="analysis-grid">
            <div class="analysis-card">
                <div class="analysis-title">📌 交易量比較</div>
                <div>{volume_text}</div>
            </div>
            <div class="analysis-card">
                <div class="analysis-title">💰 價格比較</div>
                <div>{price_text}</div>
            </div>
            <div class="analysis-card">
                <div class="analysis-title">📈 近期變化</div>
                <div>{trend_text}</div>
            </div>
        </div>

        <div class="judgment-box">
            <h3>🤖 房仲市場判讀</h3>
            <p><strong>整體判讀：</strong>{volume_text}{price_text}{trend_text}</p>
            <p><strong>賣方策略：</strong>{seller_advice}</p>
            <p><strong>買方策略：</strong>{buyer_advice}</p>
            <p><strong>開發重點：</strong>優先追蹤交易量較高的行政區與熱門路段，並針對近期價格修正明顯、但交易仍活躍的產品建立待開發名單。</p>
            <p class="analysis-note">⚠️ {html_escape(sample_note)}</p>
        </div>

        <div class="hot-route-box">
            <h3>🔥 各區目前最活躍路段</h3>
            <ul>{route_html}</ul>
        </div>
    </section>
    """

def build_stage12_alerts(report):
    """
    第12階段：
    路段異常警報＋房仲開發名單。
    所有數字均由 report 動態計算。
    """
    rows = []
    alerts = []
    development = []

    for district, data in report.get("districts", {}).items():
        for item in data.get("route_monitor", []):
            item = dict(item)
            item["district"] = district
            development.append(item)

            price_change = item.get("price_change")
            volume_change = item.get("volume_change")
            latest_count = item.get("latest_count", 0)

            if (
                price_change is not None
                and price_change <= -10
                and latest_count >= 2
                and (item.get("route_age_months") is None or item.get("route_age_months") <= 3)
            ):
                alerts.append({
                    "level": "高",
                    "district": district,
                    "route": item["route"],
                    "message": (
                        f"{district}{item['route']}最新月份平均單價"
                        f"{price_change:+.2f}%，出現明顯短期價格修正訊號。"
                    ),
                    "reason": "至少2筆最新月份交易",
                })

            if (
                volume_change is not None
                and volume_change >= 100
                and latest_count >= 2
                and (item.get("route_age_months") is None or item.get("route_age_months") <= 3)
            ):
                alerts.append({
                    "level": "中",
                    "district": district,
                    "route": item["route"],
                    "message": (
                        f"{district}{item['route']}最新月份交易量"
                        f"{volume_change:+.0f}%，交易活躍度明顯增加。"
                    ),
                    "reason": "與前一有資料月份比較",
                })

            gap = item.get("price_gap_vs_district_median")
            if (
                gap is not None
                and gap <= -15
                and latest_count >= 2
                and (item.get("route_age_months") is None or item.get("route_age_months") <= 3)
            ):
                alerts.append({
                    "level": "中",
                    "district": district,
                    "route": item["route"],
                    "message": (
                        f"{district}{item['route']}平均單價約比行政區中位數低"
                        f"{abs(gap):.1f}%，可列入價格帶研究名單。"
                    ),
                    "reason": "路段平均價與行政區中位數比較",
                })

    development.sort(
        key=lambda x: x.get("development_score", 0),
        reverse=True
    )

    top_development = development[:10]

    if not top_development:
        return """
        <section class="stage12">
            <h2>🚨 房市異常警報＋房仲開發名單</h2>
            <div class="analysis-note">
                目前沒有足夠的路段資料產生第12階段分析。
            </div>
        </section>
        """

    alert_rows = ""
    for index, item in enumerate(alerts[:12], start=1):
        level = item["level"]
        level_class = (
            "alert-high" if level == "高"
            else "alert-medium"
        )

        alert_rows += f"""
        <tr>
            <td>{index}</td>
            <td>{html_escape(item['district'])}</td>
            <td>{html_escape(item['route'])}</td>
            <td>
                <span class="alert-badge {level_class}">
                    {level}
                </span>
            </td>
            <td>{html_escape(item['message'])}</td>
            <td>{html_escape(item['reason'])}</td>
        </tr>
        """

    if not alert_rows:
        alert_rows = """
        <tr>
            <td colspan="6">
                目前沒有達到警報門檻的路段。
                這不代表市場沒有變化，而是目前資料未達到設定的異常門檻。
            </td>
        </tr>
        """

    development_rows = ""
    for index, item in enumerate(top_development, start=1):
        price_change = item.get("price_change")
        volume_change = item.get("volume_change")

        price_text = (
            "—"
            if price_change is None
            else f"{price_change:+.2f}%"
        )

        volume_text = (
            "—"
            if volume_change is None
            else f"{volume_change:+.0f}%"
        )

        age = item.get("route_age_months")
        if age is None:
            age_text = "—"
        elif age == 0:
            age_text = "本期"
        else:
            age_text = f"{age}個月前"

        development_rows += f"""
        <tr>
            <td><strong>{index}</strong></td>
            <td>{html_escape(item['district'])}</td>
            <td><strong>{html_escape(item['route'])}</strong></td>
            <td>{item.get('count', 0)} 筆</td>
            <td>{money(item.get('average'))}</td>
            <td>{price_text}</td>
            <td>{volume_text}</td>
            <td>{age_text}</td>
            <td>
                <strong class="score">
                    {item.get('development_score', 0):.1f}
                </strong>
            </td>
        </tr>
        """

    top = top_development[0]

    if alerts:
        action_text = (
            f"目前共有 {len(alerts)} 個路段達到異常警報門檻，"
            "建議優先檢查成交明細與同路段競品。"
        )
    else:
        action_text = (
            "目前沒有路段達到異常警報門檻，"
            "建議以開發分數較高的路段作為日常追蹤重點。"
        )

    return f"""
    <section class="stage12">

        <h2>🚨 第12階段｜房市異常警報＋房仲開發名單</h2>

        <div class="stage12-summary">
            <div class="stage12-card">
                <div class="stage12-title">🚨 異常警報</div>
                <div class="stage12-value">{len(alerts)}</div>
                <div>個路段</div>
            </div>

            <div class="stage12-card">
                <div class="stage12-title">🔥 第一開發優先</div>
                <div class="stage12-value">
                    {html_escape(top['route'])}
                </div>
                <div>
                    {html_escape(top['district'])}
                </div>
            </div>

            <div class="stage12-card">
                <div class="stage12-title">🎯 開發分數</div>
                <div class="stage12-value">
                    {top.get('development_score', 0):.1f}
                </div>
                <div>滿分100</div>
            </div>

            <div class="stage12-card">
                <div class="stage12-title">📊 監控路段</div>
                <div class="stage12-value">
                    {len(development)}
                </div>
                <div>個</div>
            </div>
        </div>

        <div class="stage12-action">
            <strong>📞 今日房仲行動：</strong>
            {html_escape(action_text)}
        </div>

        <h3>🚨 路段異常警報</h3>

        <div class="table-scroll">
        <table class="stage12-table">
            <tr>
                <th>排名</th>
                <th>行政區</th>
                <th>路段</th>
                <th>等級</th>
                <th>警報內容</th>
                <th>判斷依據</th>
            </tr>
            {alert_rows}
        </table>
        </div>

        <h3>🔥 今日房仲開發優先名單 Top 10</h3>

        <div class="table-scroll">
        <table class="stage12-table">
            <tr>
                <th>排名</th>
                <th>行政區</th>
                <th>路段</th>
                <th>交易量</th>
                <th>平均單價</th>
                <th>最新價格變化</th>
                <th>交易量變化</th>
                <th>資料新鮮度</th>
                <th>開發分數</th>
            </tr>
            {development_rows}
        </table>
        </div>

        <div class="stage12-note">
            ⚠️ 本階段屬於「路段監控與開發排序」，不是單一物件估價。
            價格異常必須再搭配屋齡、樓層、坪數、格局、車位及個案條件確認。
            若最新月份交易筆數過少，系統會降低警報判斷的可信度。
        </div>

    </section>
    """

def build_opportunity_data(report):
    """
    將既有路段監控資料轉成「市場機會分數」。

    這是房仲內部的開發排序工具，不是單一物件估價。
    分數綜合：交易活躍度、資料新鮮度、量能變化、價格修正、
    相對行政區價格位置；並產生可直接執行的開發理由。
    """
    district_results = []
    route_results = []

    for district, data in report.get("districts", {}).items():
        stats = data.get("stats", {})
        routes = data.get("route_monitor", []) or []
        trend = data.get("trend", {}) or {}

        count = int(stats.get("count") or 0)
        avg = to_float(stats.get("average_price"))
        median_price = to_float(stats.get("median_price"))
        recent_change = to_float(trend.get("change"))
        confidence = trend.get("confidence", "低")

        # 行政區機會分數：用於士林／北投比較，不代表房價高低。
        volume_score = min(count / 30, 1.0) * 30
        freshness_scores = []
        for r in routes:
            age = r.get("route_age_months")
            if age is None:
                freshness_scores.append(0)
            elif age <= 1:
                freshness_scores.append(20)
            elif age <= 3:
                freshness_scores.append(16)
            elif age <= 6:
                freshness_scores.append(10)
            else:
                freshness_scores.append(4)
        freshness_score = max(freshness_scores, default=0)

        if recent_change is None:
            trend_score = 8
        elif -10 <= recent_change <= 5:
            trend_score = 20
        elif recent_change < -10:
            trend_score = 15
        else:
            trend_score = 12

        active_route_count = sum(1 for r in routes if (r.get("latest_count") or 0) >= 2)
        route_score = min(active_route_count / 5, 1.0) * 20
        confidence_score = {"高": 10, "中": 7, "低": 4}.get(confidence, 4)

        district_score = round(
            min(30, volume_score)
            + freshness_score
            + trend_score
            + route_score
            + confidence_score,
            1,
        )

        district_results.append({
            "district": district,
            "score": district_score,
            "count": count,
            "average": avg,
            "median": median_price,
            "recent_change": recent_change,
            "confidence": confidence,
            "active_routes": active_route_count,
        })

        for route in routes:
            item = dict(route)
            price_change = to_float(item.get("price_change"))
            volume_change = to_float(item.get("volume_change"))
            latest_count = int(item.get("latest_count") or 0)
            gap = to_float(item.get("price_gap_vs_district_median"))
            age = item.get("route_age_months")

            activity = min((item.get("count") or 0) / 8, 1.0) * 30

            if age is None:
                freshness = 4
            elif age <= 1:
                freshness = 20
            elif age <= 3:
                freshness = 16
            elif age <= 6:
                freshness = 10
            else:
                freshness = 4

            if volume_change is None or latest_count < 2:
                volume_score = 5
            elif volume_change >= 100:
                volume_score = 15
            elif volume_change >= 50:
                volume_score = 12
            elif volume_change >= 20:
                volume_score = 9
            elif volume_change >= 0:
                volume_score = 7
            else:
                volume_score = 4

            # 「價格修正＋仍有交易」視為房仲值得研究的開發訊號，
            # 不是判定房價一定會反彈。
            if price_change is None:
                price_score = 6
            elif -20 <= price_change <= -5 and latest_count >= 2:
                price_score = 20
            elif price_change < -20 and latest_count >= 2:
                price_score = 14
            elif 5 <= price_change <= 15 and latest_count >= 2:
                price_score = 10
            else:
                price_score = 7

            if gap is not None and gap <= -15:
                relative_score = 15
            elif gap is not None and gap <= -5:
                relative_score = 11
            elif gap is not None and gap <= 5:
                relative_score = 8
            else:
                relative_score = 5

            score = round(
                activity + freshness + volume_score + price_score + relative_score,
                1,
            )

            reasons = []
            actions = []
            if latest_count >= 2:
                reasons.append(f"最新月份{latest_count}筆交易")
            if volume_change is not None and volume_change >= 50:
                reasons.append(f"量能{volume_change:+.0f}%")
                actions.append("優先追蹤近期新增案源")
            if price_change is not None and -20 <= price_change <= -5 and latest_count >= 2:
                reasons.append(f"短期價格修正{price_change:+.1f}%")
                actions.append("研究議價空間與同路段競品")
            if gap is not None and gap <= -15:
                reasons.append(f"低於行政區中位數{abs(gap):.1f}%")
                actions.append("建立價格帶／低總價開發名單")
            if age is not None and age <= 1:
                reasons.append("資料新鮮")
                actions.append("優先安排屋主／市場接觸")

            if not reasons:
                reasons.append("交易資料可追蹤")
            if not actions:
                actions.append("持續觀察，不急於下結論")

            if score >= 75:
                priority = "A｜立即追蹤"
            elif score >= 60:
                priority = "B｜本週追蹤"
            else:
                priority = "C｜一般觀察"

            item.update({
                "district": district,
                "opportunity_score": score,
                "priority": priority,
                "opportunity_reasons": reasons,
                "recommended_actions": actions,
            })
            route_results.append(item)

    district_results.sort(key=lambda x: x["score"], reverse=True)
    route_results.sort(key=lambda x: x["opportunity_score"], reverse=True)

    return {
        "districts": district_results,
        "routes": route_results[:20],
    }

def build_stage14_opportunity_board(report):
    """建立第14階段市場機會雷達 HTML。"""
    opportunity = build_opportunity_data(report)
    districts = opportunity.get("districts", [])
    routes = opportunity.get("routes", [])

    if not districts and not routes:
        return """
        <section class="stage14">
            <h2>🎯 第14階段｜市場機會雷達</h2>
            <div class="analysis-note">目前沒有足夠資料建立市場機會排序。</div>
        </section>
        """

    district_cards = ""
    for item in districts:
        change = item.get("recent_change")
        change_text = "—" if change is None else f"{change:+.2f}%"
        district_cards += f"""
        <div class="stage14-district-card">
            <div class="stage14-card-title">{html_escape(item['district'])}</div>
            <div class="stage14-score">{item['score']:.1f}<small>/100</small></div>
            <div>交易量：{item['count']} 筆</div>
            <div>近期價格變化：{change_text}</div>
            <div>活躍路段：{item['active_routes']} 個</div>
            <div>樣本可信度：{html_escape(item['confidence'])}</div>
        </div>
        """

    route_rows = ""
    for index, item in enumerate(routes[:10], start=1):
        reasons = "；".join(item.get("opportunity_reasons", [])[:3])
        actions = "；".join(item.get("recommended_actions", [])[:2])
        score = item.get("opportunity_score", 0)
        priority = item.get("priority", "C｜一般觀察")
        badge_class = "stage14-a" if priority.startswith("A") else ("stage14-b" if priority.startswith("B") else "stage14-c")
        route_rows += f"""
        <tr>
            <td><strong>{index}</strong></td>
            <td>{html_escape(item.get('district'))}</td>
            <td><strong>{html_escape(item.get('route'))}</strong></td>
            <td>{item.get('count', 0)} 筆</td>
            <td>{money(item.get('average'))}</td>
            <td><strong class="stage14-score-text">{score:.1f}</strong></td>
            <td><span class="stage14-badge {badge_class}">{html_escape(priority)}</span></td>
            <td>{html_escape(reasons)}</td>
            <td>{html_escape(actions)}</td>
        </tr>
        """

    top = routes[0] if routes else None
    if top:
        action = (
            f"今日第一優先：{top['district']} × {top['route']}，"
            f"機會分數 {top['opportunity_score']:.1f}。"
            "若實際案源條件吻合，建議先查同路段近期成交與在售競品，再安排開發。"
        )
    else:
        action = "目前沒有足夠路段資料，先以行政區機會分數與熱門路段持續觀察。"

    return f"""
    <section class="stage14">
        <h2>🎯 第14階段｜市場機會雷達＋房仲開發行動</h2>

        <div class="stage14-action">
            <strong>📞 今日行動：</strong>{html_escape(action)}
        </div>

        <h3>🏆 士林／北投市場機會分數</h3>
        <div class="stage14-district-grid">
            {district_cards}
        </div>

        <h3>🔥 今日房仲開發機會 Top 10</h3>
        <div class="table-scroll">
        <table class="stage14-table">
            <tr>
                <th>排名</th>
                <th>行政區</th>
                <th>路段</th>
                <th>交易量</th>
                <th>平均單價</th>
                <th>機會分數</th>
                <th>優先級</th>
                <th>主要訊號</th>
                <th>建議行動</th>
            </tr>
            {route_rows or '<tr><td colspan="9">目前沒有足夠路段資料。</td></tr>'}
        </table>
        </div>

        <div class="stage14-note">
            ⚠️ 機會分數是「房仲開發排序模型」，不是物件估價，也不是投資報酬率預測。
            分數越高代表目前資料呈現較值得優先研究的路段；實際開發仍需核對屋齡、樓層、坪數、格局、車位、產品類型與個案成交條件。
        </div>
    </section>
    """

def build_stage15_development_data(report):
    """
    將第14階段的市場機會路段，進一步轉成「每日房仲開發行動名單」。

    注意：這不是在售物件名單，也不是單一物件估價。
    目前以成交路段資料建立優先順序；等後續接入在售資料後，
    可再把路段優先級細化到個別物件。
    """
    opportunity = report.get("opportunity") or build_opportunity_data(report)
    routes = opportunity.get("routes", []) or []
    actions = []

    for rank, item in enumerate(routes[:20], start=1):
        score = float(item.get("opportunity_score") or 0)
        district = item.get("district") or "—"
        route = item.get("route") or "—"
        count = int(item.get("count") or 0)
        latest_count = int(item.get("latest_count") or 0)
        price_change = to_float(item.get("price_change"))
        volume_change = to_float(item.get("volume_change"))
        gap = to_float(item.get("price_gap_vs_district_median"))
        age = item.get("route_age_months")

        reasons = []
        action_list = []

        if latest_count >= 3:
            reasons.append(f"最新月份{latest_count}筆")
            action_list.append("優先查近期成交與同路段在售")
        elif latest_count >= 2:
            reasons.append(f"最新月份{latest_count}筆")
            action_list.append("建立路段屋主追蹤名單")

        if volume_change is not None and volume_change >= 50:
            reasons.append(f"交易量{volume_change:+.0f}%")
            action_list.append("優先找新增案源")

        if price_change is not None and price_change <= -10 and latest_count >= 2:
            reasons.append(f"短期價格{price_change:+.1f}%")
            action_list.append("檢查議價空間與價格修正個案")
        elif price_change is not None and price_change >= 10 and latest_count >= 2:
            reasons.append(f"短期價格{price_change:+.1f}%")
            action_list.append("確認高價成交是否具產品條件差異")

        if gap is not None and gap <= -10:
            reasons.append(f"低於行政區中位數{abs(gap):.1f}%")
            action_list.append("搜尋相對低價物件與屋主開發機會")

        if age is not None and age <= 1:
            reasons.append("最新資料")
            action_list.append("列入今日優先電話／拜訪名單")

        if not reasons:
            reasons.append("路段交易資料可追蹤")
        if not action_list:
            action_list.append("本週持續追蹤成交與在售變化")

        if score >= 75:
            priority = "A｜今天處理"
        elif score >= 60:
            priority = "B｜本週處理"
        else:
            priority = "C｜持續觀察"

        # 每日實戰順序：先查資料，再接觸屋主，最後建立追蹤。
        workflow = [
            "① 查近期成交",
            "② 比對目前在售",
            "③ 建立屋主名單",
            "④ 設定回訪日期",
        ]

        actions.append({
            "rank": rank,
            "district": district,
            "route": route,
            "score": round(score, 1),
            "priority": priority,
            "transaction_count": count,
            "latest_count": latest_count,
            "average": item.get("average"),
            "price_change": price_change,
            "volume_change": volume_change,
            "price_gap_vs_district_median": gap,
            "reasons": reasons[:4],
            "actions": action_list[:3],
            "workflow": workflow,
        })

    # 每日執行優先順序：A → B → C，再以分數排序。
    priority_order = {"A｜今天處理": 0, "B｜本週處理": 1, "C｜持續觀察": 2}
    actions.sort(key=lambda x: (priority_order.get(x["priority"], 9), -x["score"]))
    for i, item in enumerate(actions[:10], start=1):
        item["daily_rank"] = i

    top = actions[0] if actions else None
    return {
        "generated_for": "每日房仲開發行動名單",
        "top10": actions[:10],
        "today_focus": top,
        "note": "目前為路段級開發名單；尚未串接個別在售物件資料。",
    }

def build_stage15_development_board(report):
    """建立第15階段每日房仲開發 Top 10 HTML。"""
    data = build_stage15_development_data(report)
    top10 = data.get("top10", [])
    focus = data.get("today_focus")

    if not top10:
        return """
        <section class="stage15">
            <h2>🎯 第15階段｜每日房仲開發 Top 10</h2>
            <div class="analysis-note">目前沒有足夠路段資料建立每日開發名單。</div>
        </section>
        """

    if focus:
        focus_text = (
            f"今日第一順位：{focus['district']} × {focus['route']}，"
            f"{focus['priority']}，機會分數 {focus['score']:.1f}。"
            "先完成近期成交與在售比對，再進入屋主開發。"
        )
    else:
        focus_text = "目前沒有明確第一順位。"

    rows = ""
    for item in top10:
        badge_class = (
            "stage15-a" if item["priority"].startswith("A")
            else "stage15-b" if item["priority"].startswith("B")
            else "stage15-c"
        )
        reasons = "；".join(item["reasons"])
        actions = "；".join(item["actions"])
        workflow = " → ".join(item["workflow"])
        price_change = "—" if item["price_change"] is None else f"{item['price_change']:+.1f}%"
        volume_change = "—" if item["volume_change"] is None else f"{item['volume_change']:+.0f}%"
        rows += f"""
        <tr>
            <td><strong>{item['daily_rank']}</strong></td>
            <td>{html_escape(item['district'])}</td>
            <td><strong>{html_escape(item['route'])}</strong></td>
            <td><strong class="stage15-score">{item['score']:.1f}</strong></td>
            <td><span class="stage15-badge {badge_class}">{html_escape(item['priority'])}</span></td>
            <td>{item['latest_count']} 筆</td>
            <td>{price_change}</td>
            <td>{volume_change}</td>
            <td>{html_escape(reasons)}</td>
            <td>{html_escape(actions)}</td>
            <td>{html_escape(workflow)}</td>
        </tr>
        """

    return f"""
    <section class="stage15">
        <h2>🎯 第15階段｜每日房仲開發 Top 10</h2>

        <div class="stage15-focus">
            <strong>📞 今日第一通電話／第一個路段：</strong>{html_escape(focus_text)}
        </div>

        <div class="stage15-summary-grid">
            <div class="stage15-summary-card">
                <div class="stage15-summary-title">🔥 今日 A 級</div>
                <strong>{sum(1 for x in top10 if x['priority'].startswith('A'))} 個</strong>
                <small>今天優先處理</small>
            </div>
            <div class="stage15-summary-card">
                <div class="stage15-summary-title">📋 今日 Top 10</div>
                <strong>{len(top10)} 個</strong>
                <small>路段級開發名單</small>
            </div>
            <div class="stage15-summary-card">
                <div class="stage15-summary-title">🏠 執行方式</div>
                <strong>4 步驟</strong>
                <small>成交 → 在售 → 屋主 → 回訪</small>
            </div>
        </div>

        <div class="table-scroll">
        <table class="stage15-table">
            <tr>
                <th>今日排名</th>
                <th>行政區</th>
                <th>路段</th>
                <th>機會分數</th>
                <th>優先級</th>
                <th>最新月量</th>
                <th>價格變化</th>
                <th>量能變化</th>
                <th>主要訊號</th>
                <th>建議行動</th>
                <th>執行流程</th>
            </tr>
            {rows}
        </table>
        </div>

        <div class="stage15-action-plan">
            <h3>📝 今日實戰執行順序</h3>
            <ol>
                <li><strong>先查成交：</strong>確認 Top 10 路段最近成交的屋齡、樓層、坪數、格局、車位與產品類型。</li>
                <li><strong>再查在售：</strong>找同路段目前開價明顯偏離近期成交的物件。</li>
                <li><strong>建立屋主名單：</strong>優先處理 A 級路段，再處理 B 級。</li>
                <li><strong>設定回訪：</strong>每個有效開發對象建立下一次聯繫日期，不讓名單只停在報表。</li>
            </ol>
        </div>

        <div class="stage15-note">
            ⚠️ 第15階段目前是「路段級開發優先順序」，不是個別在售物件名單，也不是屋主身份判定。
            實際接觸前仍須核對物件條件與最新市場資訊。下一階段可把在售物件資料接進來，進一步產生「個別物件開發 Top 10」。
        </div>
    </section>
    """

def build_trend_and_price_band_section(report):
    """建立多期間趨勢與價格帶分析區塊。"""
    sections = []

    for district in TARGET_DISTRICTS:
        data = report.get("districts", {}).get(district)
        if not data:
            continue

        windows = data.get("trend_windows", {})
        bands = data.get("price_bands", [])
        latest = data.get("latest_transaction_date")

        trend_rows = ""
        for window in (3, 6, 12):
            info = windows.get(str(window), {})
            count = info.get("count", 0)
            change = info.get("change")
            start_month = info.get("start_month") or "—"
            end_month = info.get("end_month") or "—"
            latest_count = info.get("latest_count", 0)

            change_text = "資料不足"
            if change is not None:
                change_text = f"{change:+.2f}%"

            period_text = (
                f"{start_month} → {end_month}"
                if count >= 2 else
                "有效月份不足，無法比較"
            )

            trend_rows += f"""
                <tr>
                    <td>近{window}個有資料月份</td>
                    <td>{count} 個</td>
                    <td>{html_escape(period_text)}</td>
                    <td>{change_text}</td>
                    <td>{latest_count} 筆</td>
                </tr>
            """

        band_rows = ""
        for band in bands:
            share = band.get("share")
            share_text = "—" if share is None else f"{share:.1f}%"
            average = band.get("average")

            band_rows += f"""
                <tr>
                    <td>{html_escape(band.get("band", "—"))}</td>
                    <td>{band.get("count", 0):,} 筆</td>
                    <td>{share_text}</td>
                    <td>{money(average)}</td>
                </tr>
            """

        top_band = build_price_band_summary(bands)
        if top_band:
            top_band_text = (
                f"目前交易量最高價格帶為「{html_escape(top_band['band'])}」，"
                f"{top_band['count']:,} 筆，占全部有效交易 "
                f"{top_band.get('share', 0):.1f}%。"
            )
        else:
            top_band_text = "目前沒有足夠交易資料建立價格帶分布。"

        sections.append(f"""
        <section class="trend-band-section">
            <h2>📊 {html_escape(district)}｜3／6／12月趨勢＋價格帶分析</h2>

            <div class="trend-band-grid">
                <div>
                    <h3>📈 多期間價格趨勢</h3>
                    <div class="table-scroll">
                    <table>
                        <tr>
                            <th>觀察期間</th>
                            <th>有效月份</th>
                            <th>比較區間</th>
                            <th>價格變化</th>
                            <th>最新月交易量</th>
                        </tr>
                        {trend_rows}
                    </table>
                    </div>
                    <p class="analysis-note">
                        ⚠️ 以上以「最近N個有資料月份」計算；若月份不連續，不視為連續月數。
                        價格變化為第一個有效月份與最新有效月份的平均單價比較。
                    </p>
                </div>

                <div>
                    <h3>💰 單價價格帶分布</h3>
                    <div class="table-scroll">
                    <table>
                        <tr>
                            <th>價格帶（萬元／坪）</th>
                            <th>交易量</th>
                            <th>占比</th>
                            <th>該價格帶平均</th>
                        </tr>
                        {band_rows}
                    </table>
                    </div>
                    <div class="band-highlight">
                        🔎 {top_band_text}
                    </div>
                </div>
            </div>
        </section>
        """)

    if not sections:
        return """
        <section class="trend-band-section">
            <h2>📊 3／6／12月趨勢＋價格帶分析</h2>
            <div class="analysis-note">目前沒有足夠行政區資料可分析。</div>
        </section>
        """

    return "".join(sections)

def load_listing_comparison():
    """讀取第20階段「在售物件 × 實價成交比價」結果。"""
    path = LISTING_COMPARISON_FILE
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None

def format_percent(value):
    if value is None:
        return "—"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "—"

def format_number(value, digits=2):
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"

def market_badge(market):
    market = market or {}
    level = html_escape(market.get("level", "無法判斷"))
    emoji = html_escape(market.get("emoji", "⚪"))
    description = html_escape(market.get("description", ""))
    return f"""
        <div class="listing-market-badge">
            <strong>{emoji} {level}</strong>
            <span>{description}</span>
        </div>
    """

def build_listing_comparison_section():
    """第22階段：把第20階段 JSON 整合進每日 HTML 報告。"""
    data = load_listing_comparison()

    if not data:
        return """
        <section class="listing-comparison">
            <h2>🏷️ 在售物件 × 實價成交比價決策板</h2>
            <div class="listing-empty">
                目前尚未找到 data/listing_comparison.json。
                請先執行第20階段在售物件 × 實價成交比價引擎。
            </div>
        </section>
        """

    summary = data.get("summary", {}) or {}
    results = data.get("results", []) or []

    generated_at = data.get("generated_at")
    generated_text = "—"
    if generated_at:
        try:
            generated_dt = datetime.fromisoformat(str(generated_at))
            generated_dt = generated_dt.astimezone(ZoneInfo("Asia/Taipei"))
            generated_text = generated_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            generated_text = str(generated_at)

    summary_cards = f"""
        <div class="listing-summary-grid">
            <div class="listing-summary-card">
                <div class="listing-summary-label">在售物件</div>
                <div class="listing-summary-value">{summary.get("listing_count", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card">
                <div class="listing-summary-label">成交比較資料</div>
                <div class="listing-summary-value">{summary.get("transaction_count", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card listing-good">
                <div class="listing-summary-label">低於市場</div>
                <div class="listing-summary-value">{summary.get("below_market", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card">
                <div class="listing-summary-label">接近／合理偏高</div>
                <div class="listing-summary-value">{summary.get("near_market", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card listing-warning">
                <div class="listing-summary-label">高於市場</div>
                <div class="listing-summary-value">{summary.get("above_market", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card">
                <div class="listing-summary-label">樣本不足</div>
                <div class="listing-summary-value">{summary.get("insufficient_sample", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
        </div>
        <div class="listing-meta">
            比價資料產生時間（台灣時間）：{html_escape(generated_text)}
        </div>
    """

    item_blocks = []

    for index, result in enumerate(results, start=1):
        listing = result.get("listing", {}) or {}
        comparison = result.get("comparison", {}) or {}
        market = comparison.get("market", {}) or {}
        recommendations = comparison.get("recommendations", {}) or {}
        comparables = comparison.get("comparables", []) or []

        listing_id = listing.get("listing_id") or f"物件 {index}"
        district = listing.get("district", "")
        title = listing.get("title") or "未命名在售物件"
        location = listing.get("location") or listing.get("street") or "未提供位置"

        comparable_rows = ""
        for comp_index, comparable in enumerate(comparables, start=1):
            comparable_rows += f"""
                <tr>
                    <td>{comp_index}</td>
                    <td>{html_escape(comparable.get("date") or "—")}</td>
                    <td>{html_escape(comparable.get("street") or comparable.get("location") or "—")}</td>
                    <td>{format_number(comparable.get("area"))}</td>
                    <td><strong>{format_number(comparable.get("unit_price"))}</strong></td>
                    <td>{format_number(comparable.get("transaction_price"))}</td>
                    <td>{html_escape(comparable.get("building_type") or "—")}</td>
                    <td>{format_number(comparable.get("score"), 0)}</td>
                </tr>
            """

        if not comparable_rows:
            comparable_rows = """
                <tr>
                    <td colspan="8" class="listing-no-data">沒有可顯示的成交比較案例。</td>
                </tr>
            """

        item_blocks.append(f"""
            <article class="listing-item">
                <div class="listing-item-header">
                    <div>
                        <div class="listing-item-number">物件 #{index}</div>
                        <h3>{html_escape(title)}</h3>
                        <div class="listing-location">
                            {html_escape(district)}｜{html_escape(location)}
                        </div>
                    </div>
                    {market_badge(market)}
                </div>

                <div class="listing-facts">
                    <div>
                        <span>建物坪數</span>
                        <strong>{format_number(listing.get("building_area"))} 坪</strong>
                    </div>
                    <div>
                        <span>目前開價單價</span>
                        <strong>{format_number(listing.get("unit_price"))} 萬／坪</strong>
                    </div>
                    <div>
                        <span>目前總價</span>
                        <strong>{format_number(listing.get("total_price"))} 萬</strong>
                    </div>
                    <div>
                        <span>比較樣本</span>
                        <strong>{comparison.get("sample_count", 0):,} 筆</strong>
                    </div>
                </div>

                <div class="listing-comparison-grid">
                    <div class="listing-analysis-card">
                        <h4>📊 成交市場基準</h4>
                        <p>市場平均：<strong>{format_number(comparison.get("market_average"))} 萬／坪</strong></p>
                        <p>市場中位數：<strong>{format_number(comparison.get("market_median"))} 萬／坪</strong></p>
                        <p>Q1：<strong>{format_number(comparison.get("q1"))} 萬／坪</strong></p>
                        <p>Q3：<strong>{format_number(comparison.get("q3"))} 萬／坪</strong></p>
                        <p>開價溢／折價：<strong>{format_percent(comparison.get("premium_percent"))}</strong></p>
                    </div>

                    <div class="listing-analysis-card">
                        <h4>💰 房仲議價決策</h4>
                        <p>買方建議價：
                            <strong>{format_number(recommendations.get("buyer_price_low"))}
                            ～ {format_number(recommendations.get("buyer_price_high"))} 萬／坪</strong>
                        </p>
                        <p>賣方市場價格帶：
                            <strong>{format_number(recommendations.get("seller_price_low"))}
                            ～ {format_number(recommendations.get("seller_price_high"))} 萬／坪</strong>
                        </p>
                        <p class="listing-note">
                            ⚠️ {html_escape(recommendations.get("note") or "—")}
                        </p>
                    </div>
                </div>

                <h4 class="listing-comparable-title">🔎 主要實價比較案例</h4>
                <div class="listing-table-wrap">
                    <table class="listing-comparable-table">
                        <tr>
                            <th>#</th>
                            <th>成交日期</th>
                            <th>路段／位置</th>
                            <th>坪數</th>
                            <th>單價</th>
                            <th>總價</th>
                            <th>建物類型</th>
                            <th>匹配分數</th>
                        </tr>
                        {comparable_rows}
                    </table>
                </div>

                <div class="listing-id">物件編號：{html_escape(listing_id)}</div>
            </article>
        """)

    item_html = "".join(item_blocks) if item_blocks else """
        <div class="listing-empty">
            比價 JSON 已成功讀取，但目前沒有在售物件分析結果。
        </div>
    """

    return f"""
    <section class="listing-comparison">
        <div class="listing-section-title">
            <div>
                <h2>🏷️ 在售物件 × 實價成交比價決策板</h2>
                <p>
                    將目前在售開價與實價成交案例放在同一張決策板，
                    協助快速判斷開價位置、買方可談區間與賣方合理價格帶。
                </p>
            </div>
        </div>

        {summary_cards}

        <div class="listing-method-note">
            <strong>比價邏輯：</strong>
            本區直接使用第20階段產生的
            <code>data/listing_comparison.json</code>，
            不重新計算成交案例，確保與獨立比價引擎一致。
        </div>

        {item_html}
    </section>
    """

def load_pricing_decisions():
    """讀取 pricing_engine.py 產生的 data/pricing_decisions.csv。

    本區只負責展示決策引擎結果，不重新計算成交案例，避免報告頁與
    第29/30階段的價格決策結果產生不一致。
    """
    path = PRICING_DECISIONS_FILE
    if not os.path.exists(path):
        return []

    rows = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if not isinstance(row, dict):
                    continue
                rows.append(row)
    except (OSError, csv.Error):
        return []
    return rows

def pricing_value(row, key):
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None

def pricing_int(row, key):
    value = pricing_value(row, key)
    if value is None:
        return 0
    return int(round(value))

def pricing_text(row, key, default="—"):
    value = row.get(key)
    if value is None or str(value).strip() == "":
        return default
    return html_escape(value)

def pricing_grade_class(grade):
    grade = str(grade or "").strip()
    if grade in ("價格偏低", "低於市場"):
        return "pricing-good"
    if grade in ("接近市場", "合理偏高", "接近／合理偏高"):
        return "pricing-neutral"
    if grade in ("偏高", "價格過高", "高於市場"):
        return "pricing-high"
    return "pricing-insufficient"

def build_pricing_decision_section():
    """把第29/30階段 pricing_decisions.csv 整合進每日報告。"""
    rows = load_pricing_decisions()

    if not rows:
        return """
        <section class="pricing-decision">
            <div class="pricing-section-title">
                <h2>💰 房仲實戰價格決策儀表板</h2>
                <p>尚未找到 data/pricing_decisions.csv。請先執行房仲實戰價格決策引擎。</p>
            </div>
        </section>
        """

    # 價格等級統計；兼容舊版與新版文字。
    counts = {
        "低於市場": 0,
        "接近市場": 0,
        "高於市場": 0,
        "樣本不足": 0,
    }
    grade_alias = {
        "價格偏低": "低於市場",
        "價格過高": "高於市場",
        "偏高": "高於市場",
        "合理偏高": "接近市場",
        "接近／合理偏高": "接近市場",
    }
    for row in rows:
        raw = str(row.get("price_grade") or "樣本不足").strip()
        bucket = grade_alias.get(raw, raw)
        if bucket not in counts:
            bucket = "樣本不足"
        counts[bucket] += 1

    total = len(rows)
    cards = f"""
        <div class="pricing-summary-grid">
            <div class="pricing-summary-card">
                <div class="pricing-summary-label">分析物件</div>
                <div class="pricing-summary-value">{total:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-good">
                <div class="pricing-summary-label">低於市場</div>
                <div class="pricing-summary-value">{counts['低於市場']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-neutral">
                <div class="pricing-summary-label">接近市場</div>
                <div class="pricing-summary-value">{counts['接近市場']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-high">
                <div class="pricing-summary-label">高於市場</div>
                <div class="pricing-summary-value">{counts['高於市場']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-insufficient">
                <div class="pricing-summary-label">樣本不足</div>
                <div class="pricing-summary-value">{counts['樣本不足']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
        </div>
        <div class="pricing-method-note">
            <strong>決策來源：</strong>直接讀取 <code>data/pricing_decisions.csv</code>，
            顯示第29/30階段價格決策引擎的結果；本頁不重新計算成交案例。
        </div>
    """

    item_blocks = []
    for index, row in enumerate(rows, start=1):
        grade = str(row.get("price_grade") or "樣本不足").strip()
        grade_class = pricing_grade_class(grade)
        confidence = str(row.get("confidence") or "低").strip()
        summary = row.get("comparable_grade_summary") or (
            f"A{pricing_int(row, 'grade_a_count')}/"
            f"B{pricing_int(row, 'grade_b_count')}/"
            f"C{pricing_int(row, 'grade_c_count')}"
        )
        current_unit = pricing_value(row, "current_unit_price")
        weighted_unit = pricing_value(row, "weighted_market_unit_price")
        median_unit = pricing_value(row, "median_transaction_unit_price")
        gap = pricing_value(row, "price_gap_percent")
        low_price = pricing_value(row, "reasonable_low_price")
        high_price = pricing_value(row, "reasonable_high_price")
        buyer_first = pricing_value(row, "buyer_first_price")
        buyer_max = pricing_value(row, "buyer_max_price")
        seller_price = pricing_value(row, "seller_reasonable_price")
        negotiation = pricing_value(row, "negotiation_percent")

        if grade == "樣本不足":
            action = "先補足同類型成交樣本，再做正式議價判斷。"
        elif grade in ("價格過高", "偏高", "高於市場"):
            action = "列入議價重點；先確認屋況、樓層、車位與裝潢差異，再以成交基準回推合理價格。"
        elif grade in ("價格偏低", "低於市場"):
            action = "價格具有吸引力，但仍應檢查是否存在特殊瑕疵、權利或產品差異。"
        else:
            action = "價格接近市場，可把重點放在產品優缺點、付款條件與議價空間。"

        comparable_info = f"""
            <div class="pricing-comparable-meta">
                <span>A級 {pricing_int(row, 'grade_a_count')} 筆</span>
                <span>B級 {pricing_int(row, 'grade_b_count')} 筆</span>
                <span>C級 {pricing_int(row, 'grade_c_count')} 筆</span>
                <span>核心 {pricing_int(row, 'core_comparable_count')} 筆</span>
                <span>排除 {pricing_int(row, 'excluded_count')} 筆</span>
            </div>
        """

        item_blocks.append(f"""
            <article class="pricing-item">
                <div class="pricing-item-header">
                    <div>
                        <div class="pricing-item-number">物件 #{index}｜{pricing_text(row, 'listing_id')}</div>
                        <h3>{pricing_text(row, 'title', '未命名在售物件')}</h3>
                        <div class="pricing-location">
                            {pricing_text(row, 'district', '')}｜{pricing_text(row, 'location', '未提供位置')}
                        </div>
                    </div>
                    <div class="pricing-badge {grade_class}">
                        <strong>{html_escape(grade)}</strong>
                        <span>信心：{html_escape(confidence)}</span>
                    </div>
                </div>

                <div class="pricing-facts">
                    <div><span>目前開價</span><strong>{money(pricing_value(row, 'current_price'))} 萬</strong></div>
                    <div><span>目前開價單價</span><strong>{money(current_unit)} 萬／坪</strong></div>
                    <div><span>加權市場單價</span><strong>{money(weighted_unit)} 萬／坪</strong></div>
                    <div><span>價格差距</span><strong>{format_percent(gap)}</strong></div>
                </div>

                <div class="pricing-decision-grid">
                    <div class="pricing-analysis-card">
                        <h4>📊 市場基準</h4>
                        <p>加權市場單價：<strong>{money(weighted_unit)} 萬／坪</strong></p>
                        <p>成交中位單價：<strong>{money(median_unit)} 萬／坪</strong></p>
                        <p>比較樣本：<strong>{pricing_int(row, 'comparable_count')} 筆</strong></p>
                        <p>案例品質：<strong>{html_escape(summary)}</strong></p>
                        {comparable_info}
                    </div>
                    <div class="pricing-analysis-card pricing-action-card">
                        <h4>💰 房仲議價決策</h4>
                        <p>合理價格：<strong>{money(low_price)} ～ {money(high_price)} 萬</strong></p>
                        <p>買方第一口：<strong>{money(buyer_first)} 萬</strong></p>
                        <p>買方最高價：<strong>{money(buyer_max)} 萬</strong></p>
                        <p>賣方合理價：<strong>{money(seller_price)} 萬</strong></p>
                        <p>理論議價幅度：<strong>{format_percent(negotiation)}</strong></p>
                    </div>
                </div>

                <div class="pricing-action-note">
                    <strong>🎯 實戰建議：</strong>{html_escape(action)}
                </div>
                <div class="pricing-safety-note">
                    ⚠️ 本區間屬資料模型的決策輔助，不代表保證成交價；樣本不足時不得把空白價格區間解讀成零元或無議價空間。
                </div>
            </article>
        """)

    return f"""
    <section class="pricing-decision">
        <div class="pricing-section-title">
            <h2>💰 房仲實戰價格決策儀表板</h2>
            <p>把「目前在售開價」與「實價成交模型」轉成可直接拿來談案、估價、議價的決策資訊。</p>
        </div>
        {cards}
        {''.join(item_blocks)}
    </section>
    """

def build_report_data(records):

    report = {

        "generated_at":
            datetime.now(ZoneInfo("Asia/Taipei")).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "districts": {},

    }

    for district in TARGET_DISTRICTS:

        items = [
            item
            for item in records
            if item["district"]
            == district
        ]

        if not items:
            continue

        stats = analyze_district(
            items
        )

        months = monthly_trend(
            items
        )

        trend = determine_trend(
            months
        )

        trend_windows = build_trend_windows(
            months
        )

        price_bands = build_price_bands(
            items
        )

        routes = route_analysis(
            items
        )

        route_monitor = route_monitor_analysis(
            items,
            stats
        )

        report["districts"][
            district
        ] = {

            "stats": stats,

            "trend": trend,

            "months": months,

            "trend_windows": trend_windows,

            "price_bands": price_bands,

            "routes": routes,
            "route_monitor": route_monitor,
            "latest_transaction_date": max(
                (item.get("date") for item in items if item.get("date")),
                default=None
            ),
            }

    # 第14階段：把市場機會排序一併寫入 JSON，
    # 方便未來接 API、LINE、Email 或其他儀表板。
    report["opportunity"] = build_opportunity_data(report)

    # 第15階段：每日房仲開發 Top 10 行動名單
    report["development_today"] = build_stage15_development_data(report)

    # 第16階段：個別成交個案開發雷達
    report["property_radar"] = build_stage16_property_radar(records, report)

    # 第17階段：接入目前在售物件；沒有資料時保持空結果，不捏造。
    listings, listing_source = load_listings()
    report["listing_radar"] = build_stage17_listing_radar(
        listings, records, report, listing_source
    )

    return report

def html_escape(value):

    text = str(value)

    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

def money(value):

    if value is None:
        return "—"

    return f"{value:,.2f}"

def build_history_chart(months, district):
    """建立單一行政區的歷史平均單價 SVG 趨勢圖。"""
    valid = []
    for item in months:
        average = item.get("average")
        if average is None:
            continue
        try:
            value = float(average)
        except (TypeError, ValueError):
            continue
        valid.append((str(item.get("month", "")), value))

    if not valid:
        return """
        <div class="history-chart">
            <h3>📈 歷史房價趨勢</h3>
            <div class="no-chart-data">目前沒有足夠的歷史月份資料可繪製趨勢圖。</div>
        </div>
        """

    width, height = 1000, 380
    left, right, top, bottom = 75, 35, 45, 75
    values = [v for _, v in valid]
    low, high = min(values), max(values)
    if high == low:
        low -= 1
        high += 1

    plot_width = width - left - right
    plot_height = height - top - bottom
    points, point_html, label_html, grid_html = [], [], [], []

    for index, (month_name, value) in enumerate(valid):
        x = left + plot_width / 2 if len(valid) == 1 else left + plot_width * index / (len(valid) - 1)
        y = top + plot_height - ((value - low) / (high - low)) * plot_height
        points.append(f"{x:.2f},{y:.2f}")
        point_html.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" class="history-point"></circle>')
        point_html.append(f'<text x="{x:.2f}" y="{max(20, y - 14):.2f}" text-anchor="middle" class="history-value">{value:.2f}</text>')
        label_html.append(f'<text x="{x:.2f}" y="{height - 30}" text-anchor="middle" class="history-label">{html_escape(month_name)}</text>')

    for index in range(5):
        ratio = index / 4
        y = top + plot_height * ratio
        value = high - (high - low) * ratio
        grid_html.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" class="history-grid"></line>')
        grid_html.append(f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" class="history-axis-label">{value:.2f}</text>')

    district_text = html_escape(district)
    return f"""
    <div class="history-chart">
        <h3>📈 歷史房價趨勢</h3>
        <div class="chart-subtitle">{district_text}｜平均單價（萬元／坪）</div>
        <div class="history-chart-box">
            <svg class="history-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="{district_text}歷史平均單價趨勢圖">
                {"".join(grid_html)}
                <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" class="history-axis"></line>
                <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="history-axis"></line>
                <polyline points="{" ".join(points)}" class="history-line" fill="none"></polyline>
                {"".join(point_html)}
                {"".join(label_html)}
            </svg>
        </div>
    </div>
    """

def create_html(report):
    # ============================================================
    # 第12-1階段：士林／北投市場總覽
    # ============================================================

    summary_rows = ""

    for district, data in report["districts"].items():

        stats = data["stats"]
        trend = data["trend"]

        change = trend.get("change")

        if change is None:
            change_text = "—"
        else:
            change_text = f"{change:+.2f}%"

        summary_rows += f"""
            <tr>
                <td>
                    <strong>{html_escape(district)}</strong>
                </td>

                <td>
                    {stats["count"]:,} 筆
                </td>

                <td>
                    {money(stats["average_price"])}
                    萬／坪
                </td>

                <td>
                    {money(stats["median_price"])}
                    萬／坪
                </td>

                <td>
                    {html_escape(trend["direction"])}
                </td>

                <td>
                    {change_text}
                </td>
            </tr>
        """

    summary = f"""
        <section class="summary">

            <h2>🏠 士林區／北投區市場總覽</h2>

            <table>

                <tr>
                    <th>行政區</th>
                    <th>交易量</th>
                    <th>平均單價</th>
                    <th>中位數</th>
                    <th>市場方向</th>
                    <th>近期變化</th>
                </tr>

                {summary_rows}

            </table>

        </section>
    """
    market_analysis = build_market_comparison(report)
    decision_dashboard = build_decision_dashboard(report)
    trend_band_analysis = build_trend_and_price_band_section(report)
    stage12_alerts = build_stage12_alerts(report)
    stage14_opportunity = build_stage14_opportunity_board(report)
    stage15_development = build_stage15_development_board(report)
    stage16_property = build_stage16_property_board(report)
    stage17_listing = build_stage17_listing_board(report)
    listing_comparison_html = build_listing_comparison_section()
    pricing_decision_html = build_pricing_decision_section()

    generated_at = report[
        "generated_at"
    ]
    latest_dates = [
        data.get("latest_transaction_date")
        for data in report["districts"].values()
        if data.get("latest_transaction_date")
    ]

    latest_transaction_date = (
        max(latest_dates)
        if latest_dates
        else None
    )

    if latest_transaction_date:
        if isinstance(latest_transaction_date, (tuple, list)):
            if len(latest_transaction_date) >= 3:
                latest_transaction_date = (
                    f"{latest_transaction_date[0]}年"
                    f"{latest_transaction_date[1]}月"
                    f"{latest_transaction_date[2]}日"
                )
            else:
                latest_transaction_date = str(latest_transaction_date)
        elif hasattr(latest_transaction_date, "strftime"):
            latest_transaction_date = latest_transaction_date.strftime("%Y年%m月%d日")
        else:
            latest_transaction_date = str(latest_transaction_date)
    else:
        latest_transaction_date = "無資料"

    cards = ""

    for district, data in report[
        "districts"
    ].items():

        stats = data["stats"]

        trend = data["trend"]

        direction = trend[
            "direction"
        ]

        change = trend[
            "change"
        ]

        confidence = trend[
            "confidence"
        ]

        if change is None:

            change_text = "—"

        else:

            change_text = (
                f"{change:+.2f}%"
            )

        # 3／6／12 個有資料月份的變化文字
        # 先在 f-string 外計算，避免 Python 3.11 對巢狀 f-string／引號解析問題。
        trend_windows = data.get("trend_windows", {})

        trend3_change = trend_windows.get("3", {}).get("change")
        trend6_change = trend_windows.get("6", {}).get("change")
        trend12_change = trend_windows.get("12", {}).get("change")

        trend3_text = "—" if trend3_change is None else f"{trend3_change:+.2f}%"
        trend6_text = "—" if trend6_change is None else f"{trend6_change:+.2f}%"
        trend12_text = "—" if trend12_change is None else f"{trend12_change:+.2f}%"

        cards += f"""
        <section class="district">

            <h2>{html_escape(district)}</h2>

            <div class="grid">

                <div class="card">
                    <div class="label">
                        有效交易
                    </div>
                    <div class="value">
                        {stats['count']:,} 筆
                    </div>
                </div>

                <div class="card">
                    <div class="label">
                        平均單價
                    </div>
                    <div class="value">
                        {money(stats['average_price'])}
                    </div>
                    <div class="unit">
                        萬元／坪
                    </div>
                </div>

                <div class="card">
                    <div class="label">
                        中位數
                    </div>
                    <div class="value">
                        {money(stats['median_price'])}
                    </div>
                    <div class="unit">
                        萬元／坪
                    </div>
                </div>

                <div class="card">
                    <div class="label">
                        主流平均
                    </div>
                    <div class="value">
                        {money(stats['normal_average'])}
                    </div>
                    <div class="unit">
                        萬元／坪
                    </div>
                </div>

            </div>

            <div class="trend">

                <h3>📈 市場趨勢</h3>

                <p>
                    <strong>
                        {html_escape(direction)}
                    </strong>
                </p>

                <p>
                    期間價格變化：
                    <strong>
                        {change_text}
                    </strong>
                </p>

                <p>
                    樣本可信度：
                    <strong>
                        {html_escape(confidence)}
                    </strong>
                </p>

            </div>

            <div class="district-mini-analysis">
                <h3>📊 3／6／12個有資料月份</h3>
                <div class="mini-period-grid">
                    <div class="mini-period">
                        <span>近3月</span>
                        <strong>{trend3_text}</strong>
                    </div>
                    <div class="mini-period">
                        <span>近6月</span>
                        <strong>{trend6_text}</strong>
                    </div>
                    <div class="mini-period">
                        <span>近12月</span>
                        <strong>{trend12_text}</strong>
                    </div>
                </div>
            </div>

            <h3>🔥 市場熱門路段</h3>

            <table>

                <tr>
                    <th>排名</th>
                    <th>路段</th>
                    <th>交易量</th>
                    <th>平均單價</th>
                    <th>熱度</th>
                </tr>
        """

        for index, route in enumerate(
            data["routes"][:10],
            start=1
        ):

            cards += f"""
                <tr>
                    <td>{index}</td>
                    <td>
                        {html_escape(route['route'])}
                    </td>
                    <td>
                        {route['count']} 筆
                    </td>
                    <td>
                        {money(route['average'])}
                    </td>
                    <td>
                        {money(route['heat'])}
                    </td>
                </tr>
            """

        cards += """
            </table>

            <h3>📊 歷史月份</h3>

            <table>

                <tr>
                    <th>月份</th>
                    <th>交易量</th>
                    <th>平均單價</th>
                    <th>中位數</th>
                    <th>月增率</th>
                </tr>
        """

        for month in data["months"]:

            change = month["change"]

            change_text = (
                f"{change:+.2f}%"
                if change is not None
                else "—"
            )

            cards += f"""
                <tr>
                    <td>
                        {month['month']}
                    </td>
                    <td>
                        {month['count']} 筆
                    </td>
                    <td>
                        {money(month['average'])}
                    </td>
                    <td>
                        {money(month['median'])}
                    </td>
                    <td>
                        {change_text}
                    </td>
                </tr>
            """

        cards += """
            </table>
        """

        cards += build_history_chart(
            data["months"],
            district,
        )

        cards += """
        </section>
        """

    html = f"""
<!DOCTYPE html>

<html lang="zh-Hant">

<head>

<meta charset="utf-8">

<meta name="viewport"
      content="width=device-width,
               initial-scale=1.0">

<title>
士林區／北投區房市每日報告
</title>

<style>

body {{
    font-family:
        Arial,
        "Microsoft JhengHei",
        sans-serif;

    margin: 0;

    background: #f3f6f9;

    color: #1f2937;
}}

header {{
    background:
        linear-gradient(
            135deg,
            #0f172a,
            #1e3a5f
        );

    color: white;

    padding: 35px 20px;

    text-align: center;
}}

header h1 {{
    margin: 0 0 10px 0;
}}

.container {{
    max-width: 1100px;

    margin: 30px auto;

    padding: 0 20px;
}}

.district {{
    background: white;

    padding: 25px;

    margin-bottom: 30px;

    border-radius: 14px;

    box-shadow:
        0 4px 15px
        rgba(0,0,0,0.08);
}}

.grid {{
    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(180px, 1fr)
        );

    gap: 15px;
}}

.card {{
    background: #f8fafc;

    padding: 20px;

    border-radius: 10px;
}}

.label {{
    color: #64748b;

    font-size: 14px;
}}

.value {{
    font-size: 25px;

    font-weight: bold;

    margin-top: 8px;
}}

.unit {{
    font-size: 13px;

    color: #64748b;
}}

.trend {{
    margin: 25px 0;

    padding: 20px;

    background: #eef6ff;

    border-left:
        5px solid #2563eb;

    border-radius: 8px;
}}

table {{
    width: 100%;

    border-collapse:
        collapse;

    margin-bottom: 25px;
}}

th,
td {{
    padding: 10px;

    border-bottom:
        1px solid #e5e7eb;

    text-align: left;
}}

th {{
    background: #f1f5f9;
}}

footer {{
    text-align: center;

    color: #64748b;

    padding: 30px;
}}

.market-analysis {{
    margin: 25px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.market-analysis h2 {{
    margin-top: 0;
}}

.market-analysis h3 {{
    margin-top: 0;
}}

.comparison-table {{
    margin-bottom: 18px;
}}

.analysis-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 18px 0;
}}

.analysis-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.8;
}}

.analysis-title {{
    color: #1d4ed8;
    font-weight: 700;
    margin-bottom: 6px;
}}

.judgment-box {{
    margin-top: 18px;
    padding: 20px;
    background: #eef6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.9;
}}

.judgment-box p {{
    margin: 8px 0;
}}

.analysis-note {{
    color: #64748b;
    font-size: 13px;
}}

.hot-route-box {{
    margin-top: 18px;
    padding: 18px;
    background: #fff7ed;
    border-left: 5px solid #f97316;
    border-radius: 10px;
}}

.hot-route-box ul {{
    margin: 8px 0 0 20px;
    padding: 0;
}}

.history-chart {{
    display: block;
    width: 100%;
    margin: 28px 0 10px 0;
}}

.history-chart h3 {{ margin: 0 0 8px 0; }}
.chart-subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 10px; }}
.history-chart-box {{ display: block; width: 100%; overflow-x: auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px; box-sizing: border-box; }}
.history-svg {{ display: block; width: 100%; min-width: 760px; height: auto; }}
.history-grid {{ stroke: #e2e8f0; stroke-width: 1; }}
.history-axis {{ stroke: #94a3b8; stroke-width: 1.2; }}
.history-line {{ stroke: #2563eb; stroke-width: 4; stroke-linejoin: round; stroke-linecap: round; }}
.history-point {{ fill: #ffffff; stroke: #2563eb; stroke-width: 3; }}
.history-label {{ fill: #475569; font-size: 12px; }}
.history-axis-label {{ fill: #64748b; font-size: 11px; }}
.history-value {{ fill: #1d4ed8; font-size: 11px; font-weight: bold; }}
.no-chart-data {{ background: #f8fafc; color: #64748b; padding: 18px; border-radius: 10px; text-align: center; }}


.decision-dashboard {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.decision-dashboard h2 {{
    margin-top: 0;
}}

.decision-summary {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 18px;
}}

.decision-summary-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.7;
}}

.decision-summary-title {{
    color: #1d4ed8;
    font-weight: 700;
    margin-bottom: 6px;
}}

.decision-summary-card small {{
    color: #64748b;
}}

.decision-metrics {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-bottom: 18px;
}}

.decision-card {{
    background: #f8fafc;
    border: 1px solid #dbeafe;
    border-radius: 10px;
    padding: 16px;
}}

.decision-card-title {{
    color: #0f172a;
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 10px;
}}

.decision-row {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 7px 0;
    border-bottom: 1px solid #e5e7eb;
}}

.decision-row:last-child {{
    border-bottom: 0;
}}

.decision-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 18px 0;
}}

.decision-panel {{
    padding: 18px;
    border-radius: 10px;
    line-height: 1.8;
}}

.decision-panel h3 {{
    margin-top: 0;
}}

.decision-panel.seller {{
    background: #fff7ed;
    border-left: 5px solid #f97316;
}}

.decision-panel.buyer {{
    background: #eff6ff;
    border-left: 5px solid #2563eb;
}}

.decision-panel.developer {{
    background: #f0fdf4;
    border-left: 5px solid #16a34a;
}}

.decision-alerts {{
    margin-top: 18px;
    padding: 18px;
    background: #f8fafc;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
}}

.decision-alerts h3 {{
    margin-top: 0;
}}

.decision-alerts li {{
    margin-bottom: 8px;
}}


.stage14 {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07);
}}

.stage14 h2 {{
    margin-top: 0;
}}

.stage14-action {{
    margin: 18px 0;
    padding: 18px;
    background: #eff6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.8;
}}

.stage14-district-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin: 18px 0 22px 0;
}}

.stage14-district-card {{
    background: #f8fafc;
    border: 1px solid #dbeafe;
    border-radius: 10px;
    padding: 18px;
    line-height: 1.8;
}}

.stage14-card-title {{
    font-size: 20px;
    font-weight: 800;
    color: #0f172a;
}}

.stage14-score {{
    margin: 4px 0 8px 0;
    font-size: 34px;
    font-weight: 900;
    color: #1d4ed8;
}}

.stage14-score small {{
    font-size: 13px;
    color: #64748b;
    margin-left: 4px;
}}

.stage14-table td, .stage14-table th {{
    vertical-align: top;
}}

.stage14-badge {{
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
}}

.stage14-a {{
    background: #fee2e2;
    color: #b91c1c;
}}

.stage14-b {{
    background: #fef3c7;
    color: #92400e;
}}

.stage14-c {{
    background: #e2e8f0;
    color: #475569;
}}

.stage14-score-text {{
    color: #1d4ed8;
}}

.stage14-note {{
    margin-top: 18px;
    padding: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    color: #64748b;
    line-height: 1.7;
}}




.stage15 {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07);
}}

.stage15 h2 {{ margin-top: 0; }}

.stage15-focus {{
    margin: 18px 0;
    padding: 18px;
    background: #fff7ed;
    border-left: 5px solid #f97316;
    border-radius: 10px;
    line-height: 1.8;
}}

.stage15-summary-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 18px 0 22px 0;
}}

.stage15-summary-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.7;
}}

.stage15-summary-title {{
    color: #1d4ed8;
    font-weight: 700;
    margin-bottom: 5px;
}}

.stage15-summary-card strong {{
    display: block;
    font-size: 25px;
    color: #0f172a;
}}

.stage15-summary-card small {{ color: #64748b; }}

.stage15-table td, .stage15-table th {{ vertical-align: top; }}
.stage15-score {{ color: #1d4ed8; }}

.stage15-badge {{
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
}}

.stage15-a {{ background: #fee2e2; color: #b91c1c; }}
.stage15-b {{ background: #fef3c7; color: #92400e; }}
.stage15-c {{ background: #e2e8f0; color: #475569; }}

.stage15-action-plan {{
    margin-top: 18px;
    padding: 18px;
    background: #eff6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.8;
}}

.stage15-action-plan h3 {{ margin-top: 0; }}
.stage15-action-plan li {{ margin-bottom: 8px; }}

.stage15-note {{
    margin-top: 18px;
    padding: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    color: #64748b;
    line-height: 1.7;
}}

.stage12 {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07);
}}

.stage12 h2 {{
    margin-top: 0;
}}

.stage12 h3 {{
    margin-top: 24px;
}}

.stage12-summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 18px 0;
}}

.stage12-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.6;
}}

.stage12-title {{
    color: #1d4ed8;
    font-weight: 700;
}}

.stage12-value {{
    margin-top: 6px;
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
}}

.stage12-action {{
    margin: 18px 0;
    padding: 18px;
    background: #eff6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.8;
}}

.stage12-table {{
    margin-bottom: 18px;
}}

.alert-badge {{
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}}

.alert-high {{
    background: #fee2e2;
    color: #b91c1c;
}}

.alert-medium {{
    background: #fef3c7;
    color: #92400e;
}}

.score {{
    color: #1d4ed8;
}}

.stage12-note {{
    margin-top: 18px;
    padding: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    color: #64748b;
    line-height: 1.7;
}}

.table-scroll {{
    overflow-x: auto;
}}


.trend-band-section {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.trend-band-section h2 {{
    margin-top: 0;
}}

.trend-band-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
}}

.band-highlight {{
    margin-top: 12px;
    padding: 14px;
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    line-height: 1.7;
}}

.district-mini-analysis {{
    margin: 18px 0;
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}}

.district-mini-analysis h3 {{
    margin-top: 0;
}}

.mini-period-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
}}

.mini-period {{
    padding: 12px;
    background: #ffffff;
    border: 1px solid #dbeafe;
    border-radius: 8px;
}}

.mini-period span {{
    display: block;
    color: #64748b;
    font-size: 13px;
}}

.mini-period strong {{
    display: block;
    margin-top: 5px;
    font-size: 18px;
    color: #1d4ed8;
}}

@media(max-width:700px) {{

    .district {{
        padding: 15px;
    }}

    table {{
        font-size: 13px;
    }}

    .trend-band-grid {{
        grid-template-columns: 1fr;
    }}

    .mini-period-grid {{
        grid-template-columns: 1fr;
    }}

    .stage15-summary-grid {{
        grid-template-columns: 1fr;
    }}

}}


.stage16 {{ margin-top: 28px; padding: 24px; background: #fff; border-radius: 18px; box-shadow: 0 4px 18px rgba(20,40,80,.08); }}
.stage16-focus {{ margin: 16px 0; padding: 18px; background: #eef6ff; border-left: 5px solid #2563eb; border-radius: 10px; line-height: 1.9; }}
.stage16 table {{ width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 14px; }}
.stage16 th, .stage16 td {{ padding: 10px 8px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }}
.stage16 th {{ background: #eef2f7; }}
.stage16-note {{ margin-top: 16px; padding: 14px; background: #fff8ed; border-left: 4px solid #f59e0b; border-radius: 8px; line-height: 1.8; }}
.stage17 {{ margin-top: 28px; padding: 24px; background: #fff; border-radius: 18px; box-shadow: 0 4px 18px rgba(20,40,80,.08); }}
.stage17-focus {{ margin: 16px 0; padding: 18px; background: #effaf3; border-left: 5px solid #16a34a; border-radius: 10px; line-height: 1.9; }}
.stage17-summary-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 16px 0; }}
.stage17-summary-card {{ padding: 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; }}
.stage17-summary-title {{ color: #2563eb; font-weight: 700; margin-bottom: 8px; }}
.stage17-summary-card strong {{ display:block; font-size: 25px; color:#0f172a; margin-bottom:4px; }}
.stage17-summary-card small {{ color:#64748b; }}
.stage17-table {{ width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 13px; }}
.stage17-table th, .stage17-table td {{ padding: 9px 7px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }}
.stage17-table th {{ background:#eef2f7; }}
.stage17-note {{ margin-top:16px; padding:14px; background:#fff8ed; border-left:4px solid #f59e0b; border-radius:8px; line-height:1.8; }}
@media(max-width:900px) {{ .stage17-summary-grid {{ grid-template-columns:1fr; }} }}


/* ===== V6.2 / V6.3 current report styles ===== */


body {{
    font-family:
        Arial,
        "Microsoft JhengHei",
        sans-serif;

    margin: 0;

    background: #f3f6f9;

    color: #1f2937;
}}

header {{
    background:
        linear-gradient(
            135deg,
            #0f172a,
            #1e3a5f
        );

    color: white;

    padding: 35px 20px;

    text-align: center;
}}

header h1 {{
    margin: 0 0 10px 0;
}}

.container {{
    max-width: 1100px;

    margin: 30px auto;

    padding: 0 20px;
}}

.district {{
    background: white;

    padding: 25px;

    margin-bottom: 30px;

    border-radius: 14px;

    box-shadow:
        0 4px 15px
        rgba(0,0,0,0.08);
}}

.grid {{
    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(180px, 1fr)
        );

    gap: 15px;
}}

.card {{
    background: #f8fafc;

    padding: 20px;

    border-radius: 10px;
}}

.label {{
    color: #64748b;

    font-size: 14px;
}}

.value {{
    font-size: 25px;

    font-weight: bold;

    margin-top: 8px;
}}

.unit {{
    font-size: 13px;

    color: #64748b;
}}

.trend {{
    margin: 25px 0;

    padding: 20px;

    background: #eef6ff;

    border-left:
        5px solid #2563eb;

    border-radius: 8px;
}}

table {{
    width: 100%;

    border-collapse:
        collapse;

    margin-bottom: 25px;
}}

th,
td {{
    padding: 10px;

    border-bottom:
        1px solid #e5e7eb;

    text-align: left;
}}

th {{
    background: #f1f5f9;
}}

footer {{
    text-align: center;

    color: #64748b;

    padding: 30px;
}}

.market-analysis {{
    margin: 25px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.market-analysis h2 {{
    margin-top: 0;
}}

.market-analysis h3 {{
    margin-top: 0;
}}

.comparison-table {{
    margin-bottom: 18px;
}}

.analysis-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 18px 0;
}}

.analysis-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.8;
}}

.analysis-title {{
    color: #1d4ed8;
    font-weight: 700;
    margin-bottom: 6px;
}}

.judgment-box {{
    margin-top: 18px;
    padding: 20px;
    background: #eef6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.9;
}}

.judgment-box p {{
    margin: 8px 0;
}}

.analysis-note {{
    color: #64748b;
    font-size: 13px;
}}

.hot-route-box {{
    margin-top: 18px;
    padding: 18px;
    background: #fff7ed;
    border-left: 5px solid #f97316;
    border-radius: 10px;
}}

.hot-route-box ul {{
    margin: 8px 0 0 20px;
    padding: 0;
}}

.history-chart {{
    display: block;
    width: 100%;
    margin: 28px 0 10px 0;
}}

.history-chart h3 {{ margin: 0 0 8px 0; }}
.chart-subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 10px; }}
.history-chart-box {{ display: block; width: 100%; overflow-x: auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px; box-sizing: border-box; }}
.history-svg {{ display: block; width: 100%; min-width: 760px; height: auto; }}
.history-grid {{ stroke: #e2e8f0; stroke-width: 1; }}
.history-axis {{ stroke: #94a3b8; stroke-width: 1.2; }}
.history-line {{ stroke: #2563eb; stroke-width: 4; stroke-linejoin: round; stroke-linecap: round; }}
.history-point {{ fill: #ffffff; stroke: #2563eb; stroke-width: 3; }}
.history-label {{ fill: #475569; font-size: 12px; }}
.history-axis-label {{ fill: #64748b; font-size: 11px; }}
.history-value {{ fill: #1d4ed8; font-size: 11px; font-weight: bold; }}
.no-chart-data {{ background: #f8fafc; color: #64748b; padding: 18px; border-radius: 10px; text-align: center; }}


.listing-comparison {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.listing-section-title h2 {{ margin: 0 0 8px 0; }}
.listing-section-title p {{ margin: 0 0 18px 0; color: #64748b; line-height: 1.8; }}

.listing-summary-grid {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 10px;
    margin: 18px 0;
}}

.listing-summary-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px;
}}

.listing-summary-card.listing-good {{ background: #f0fdf4; border-color: #bbf7d0; }}
.listing-summary-card.listing-warning {{ background: #fff7ed; border-color: #fed7aa; }}
.listing-summary-label {{ color: #64748b; font-size: 13px; }}
.listing-summary-value {{ margin-top: 5px; font-size: 23px; font-weight: 700; }}
.listing-summary-unit {{ color: #64748b; font-size: 12px; }}
.listing-meta {{ color: #64748b; font-size: 12px; margin: 4px 0 18px 0; }}

.listing-method-note {{
    margin: 16px 0 20px 0;
    padding: 14px 16px;
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    color: #475569;
    line-height: 1.7;
}}

.listing-method-note code {{
    background: #e2e8f0;
    padding: 2px 5px;
    border-radius: 4px;
}}

.listing-item {{
    margin-top: 22px;
    padding: 20px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background: #ffffff;
}}

.listing-item-header {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
}}

.listing-item-number {{ color: #2563eb; font-size: 12px; font-weight: 700; margin-bottom: 4px; }}
.listing-item-header h3 {{ margin: 0 0 6px 0; }}
.listing-location {{ color: #64748b; font-size: 13px; }}

.listing-market-badge {{
    min-width: 180px;
    padding: 12px 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}}

.listing-market-badge strong {{ display: block; margin-bottom: 4px; }}
.listing-market-badge span {{ display: block; color: #64748b; font-size: 12px; line-height: 1.5; }}

.listing-facts {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 18px 0;
}}

.listing-facts > div {{ padding: 12px; background: #f8fafc; border-radius: 8px; }}
.listing-facts span {{ display: block; color: #64748b; font-size: 12px; margin-bottom: 5px; }}
.listing-facts strong {{ font-size: 17px; }}

.listing-comparison-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin: 16px 0;
}}

.listing-analysis-card {{
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    line-height: 1.7;
}}

.listing-analysis-card h4 {{ margin: 0 0 8px 0; }}
.listing-analysis-card p {{ margin: 5px 0; }}
.listing-note {{ color: #64748b; font-size: 13px; }}
.listing-comparable-title {{ margin: 20px 0 10px 0; }}
.listing-table-wrap {{ width: 100%; overflow-x: auto; }}
.listing-comparable-table {{ min-width: 850px; }}
.listing-comparable-table th, .listing-comparable-table td {{ white-space: nowrap; }}
.listing-no-data {{ text-align: center; color: #64748b; padding: 18px; }}
.listing-id {{ margin-top: 10px; color: #94a3b8; font-size: 11px; }}

.listing-empty {{
    padding: 18px;
    background: #f8fafc;
    color: #64748b;
    border-radius: 10px;
    line-height: 1.7;
}}



.pricing-decision {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.pricing-section-title h2 {{ margin: 0 0 8px 0; }}
.pricing-section-title p {{ margin: 0 0 18px 0; color: #64748b; line-height: 1.8; }}

.pricing-summary-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin: 18px 0;
}}

.pricing-summary-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px;
}}
.pricing-summary-card.pricing-good {{ background: #f0fdf4; border-color: #bbf7d0; }}
.pricing-summary-card.pricing-neutral {{ background: #eff6ff; border-color: #bfdbfe; }}
.pricing-summary-card.pricing-high {{ background: #fff7ed; border-color: #fed7aa; }}
.pricing-summary-card.pricing-insufficient {{ background: #f8fafc; border-color: #cbd5e1; }}
.pricing-summary-label {{ color: #64748b; font-size: 13px; }}
.pricing-summary-value {{ margin-top: 5px; font-size: 23px; font-weight: 700; }}
.pricing-summary-unit {{ color: #64748b; font-size: 12px; }}

.pricing-method-note {{
    margin: 16px 0 20px 0;
    padding: 14px 16px;
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    color: #475569;
    line-height: 1.7;
}}
.pricing-method-note code {{ background: #e2e8f0; padding: 2px 5px; border-radius: 4px; }}

.pricing-item {{
    margin-top: 22px;
    padding: 20px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background: #ffffff;
}}
.pricing-item-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
.pricing-item-number {{ color: #2563eb; font-size: 12px; font-weight: 700; margin-bottom: 4px; }}
.pricing-item-header h3 {{ margin: 0 0 6px 0; }}
.pricing-location {{ color: #64748b; font-size: 13px; }}

.pricing-badge {{
    min-width: 150px;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
}}
.pricing-badge strong {{ display: block; margin-bottom: 4px; }}
.pricing-badge span {{ display: block; color: #64748b; font-size: 12px; }}
.pricing-badge.pricing-good {{ background: #f0fdf4; border-color: #86efac; }}
.pricing-badge.pricing-neutral {{ background: #eff6ff; border-color: #93c5fd; }}
.pricing-badge.pricing-high {{ background: #fff7ed; border-color: #fdba74; }}
.pricing-badge.pricing-insufficient {{ background: #f8fafc; border-color: #cbd5e1; }}

.pricing-facts {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 18px 0;
}}
.pricing-facts > div {{ padding: 12px; background: #f8fafc; border-radius: 8px; }}
.pricing-facts span {{ display: block; color: #64748b; font-size: 12px; margin-bottom: 5px; }}
.pricing-facts strong {{ font-size: 17px; }}

.pricing-decision-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin: 16px 0;
}}
.pricing-analysis-card {{
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    line-height: 1.7;
}}
.pricing-analysis-card h4 {{ margin: 0 0 8px 0; }}
.pricing-analysis-card p {{ margin: 5px 0; }}
.pricing-action-card {{ background: #f0fdf4; border-color: #bbf7d0; }}
.pricing-comparable-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
.pricing-comparable-meta span {{ background: #e2e8f0; padding: 3px 7px; border-radius: 999px; font-size: 11px; color: #475569; }}
.pricing-action-note {{ margin-top: 14px; padding: 14px 16px; background: #eff6ff; border-left: 4px solid #2563eb; border-radius: 8px; line-height: 1.8; }}
.pricing-safety-note {{ margin-top: 10px; color: #64748b; font-size: 12px; line-height: 1.7; }}

@media(max-width:700px) {{

    .district {{
        padding: 15px;
    }}

    table {{
        font-size: 13px;
    }}

    .listing-summary-grid {{
        grid-template-columns: repeat(2, 1fr);
    }}

    .listing-item-header {{
        display: block;
    }}

    .listing-market-badge {{
        margin-top: 12px;
        min-width: 0;
    }}

    .listing-facts {{
        grid-template-columns: repeat(2, 1fr);
    }}

    .listing-comparison-grid {{
        grid-template-columns: 1fr;
    }}

}}


</style>

</head>

<body>

<header>

<h1>
🏠 士林區／北投區房市每日監控報告
</h1>

<p>
產生時間：
{html_escape(generated_at)}
</p>

<p>
房價資料截至：
{html_escape(latest_transaction_date)}
</p>

</header>

    <div class="container">

        {summary}

        {market_analysis}

        {decision_dashboard}

        {trend_band_analysis}

        {stage12_alerts}

        {stage14_opportunity}

        {stage15_development}

        {stage16_property}

        {stage17_listing}

        {listing_comparison_html}

        {pricing_decision_html}

        {cards}

    </div>

<footer>

台北市士林區／北投區房市監控系統<br>

第18階段：完整房市專業報告＋房仲開發作戰儀表板

</footer>

</body>

</html>
"""

    return html

def save_reports(report):

    os.makedirs(
        REPORT_DIR,
        exist_ok=True
    )

    today = datetime.now(ZoneInfo("Asia/Taipei")).strftime(
        "%Y-%m-%d"
    )

    json_file = os.path.join(
        REPORT_DIR,
        f"{today}.json"
    )

    html_file = os.path.join(
        REPORT_DIR,
        f"{today}.html"
    )

    latest_file = os.path.join(
        REPORT_DIR,
        "latest.html"
    )

    with open(
        json_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2
        )

    html = create_html(
        report
    )

    with open(
        html_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(html)

    with open(
        latest_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(html)

    print()
    print("=" * 70)
    print("第18階段完整房市報告完成")
    print("=" * 70)

    print()
    print(
        f"HTML 報告：{html_file}"
    )

    print(
        f"最新報告：{latest_file}"
    )

    print(
        f"JSON 資料：{json_file}"
    )

    print()
    print(
        "可以在 GitHub 的 reports "
        "資料夾查看報告。"
    )

    print("=" * 70)

def main():

    print()
    print("=" * 70)

    print(
        "台北市士林區／北投區"
        "每日房市專業報告引擎"
    )

    print("=" * 70)

    records = load_records()

    print()
    print(
        f"有效住宅買賣資料："
        f"{len(records):,} 筆"
    )

    if not records:

        print(
            "沒有可以產生報告的資料。"
        )

        return

    report = build_report_data(
        records
    )

    save_reports(
        report
    )

if __name__ == "__main__":
    main()
