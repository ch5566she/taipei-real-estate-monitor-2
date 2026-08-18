# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統

第八階段：
歷史價格趨勢＋路段趨勢＋住宅類型＋市場熱點分析

功能：
1. 資料品質檢查
2. 士林區／北投區住宅買賣分析
3. IQR 異常交易偵測
4. 住宅類型分析
5. 單價區間分析
6. 路段平均單價分析
7. 路段交易量分析
8. 路段市場熱度分析
9. 路段＋住宅類型交叉分析
10. 士林／北投價格比較
11. 月份歷史價格趨勢
12. 月增率分析
13. 路段歷史趨勢
14. 市場方向判斷
15. 自動處理多種日期格式

重要欄位：
uprice = 交易單價（萬元／坪）
price  = 交易總價（萬元）
tprice = 備用總價欄位
farea  = 建物移轉總面積（坪）
buitype = 建物型態
location = 地址
fdate / sdate = 日期欄位
"""

import csv
import os
import re
from collections import defaultdict
from statistics import mean, median


# ============================================================
# 基本設定
# ============================================================

INPUT_FILE = "data/taipei_transactions.csv"

TARGET_DISTRICTS = {
    "士林區",
    "北投區",
}

# 歷史趨勢至少需要多少筆交易
MIN_TREND_TRANSACTIONS = 2

# 路段至少需要幾筆交易才列入趨勢
MIN_ROUTE_TRANSACTIONS = 2


# ============================================================
# 數字轉換
# ============================================================

def to_float(value):

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    invalid_values = {
        "無",
        "無資料",
        "N/A",
        "NA",
        "None",
        "null",
        "-",
        "--",
    }

    if value in invalid_values:
        return None

    value = value.replace(",", "")
    value = value.replace("，", "")

    try:
        return float(value)

    except (ValueError, TypeError):
        return None


# ============================================================
# 日期解析
# ============================================================

def parse_date(value):
    """
    自動辨識：
    2026-08-01
    2026/08/01
    2026.08.01
    2026年8月1日
    115/08/01
    115-08-01
    1150801
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # 去除時間
    text = text.split(" ")[0]

    # 中文日期
    text = (
        text.replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
    )

    # ROC 日期
    match = re.match(
        r"^(\d{2,3})[-/.](\d{1,2})[-/.](\d{1,2})$",
        text
    )

    if match:

        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))

        if year < 1911:
            year += 1911

        return (
            year,
            month,
            day
        )

    # 西元日期
    match = re.match(
        r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$",
        text
    )

    if match:

        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))

        return (
            year,
            month,
            day
        )

    # 純數字日期
    digits = re.sub(
        r"\D",
        "",
        text
    )

    if len(digits) == 7:

        # 民國年月日
        year = int(digits[:3])
        month = int(digits[3:5])
        day = int(digits[5:7])

        year += 1911

        return (
            year,
            month,
            day
        )

    if len(digits) == 8:

        year = int(digits[:4])
        month = int(digits[4:6])
        day = int(digits[6:8])

        return (
            year,
            month,
            day
        )

    return None


def date_to_month(date_value):

    if not date_value:
        return None

    year, month, day = date_value

    return f"{year:04d}-{month:02d}"


# ============================================================
# 日期欄位自動尋找
# ============================================================

def get_transaction_date(row):

    # 優先順序
    date_fields = [
        "sdate",
        "fdate",
        "transaction_date",
        "trade_date",
        "date",
        "_importdate",
    ]

    for field in date_fields:

        value = row.get(field)

        parsed = parse_date(value)

        if parsed:
            return parsed

    return None


# ============================================================
# 地址 → 路段
# ============================================================

def extract_route(location):

    if not location:
        return "未知路段"

    text = str(location).strip()

    if not text:
        return "未知路段"

    # 移除地號
    text = re.sub(
        r"\d{3,5}-\d{4,5}地號",
        "",
        text
    )

    # 常見道路名稱
    patterns = [
        r"[\u4e00-\u9fff]{2,8}路\d*段?",
        r"[\u4e00-\u9fff]{2,8}街",
        r"[\u4e00-\u9fff]{2,8}大道",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            route = match.group(0)

            route = re.sub(
                r"\d+$",
                "",
                route
            )

            return route

    # 如果抓不到，取前面一部分
    parts = re.split(
        r"\d+號|\d+巷|\d+弄",
        text
    )

    if parts:

        result = parts[0].strip()

        if result:
            return result

    return "未知路段"


# ============================================================
# 住宅類型
# ============================================================

def normalize_building_type(row):

    building_type = str(
        row.get("buitype", "")
    ).strip()

    if building_type:
        return building_type

    return "其他"


# ============================================================
# 讀取資料
# ============================================================

def load_data():

    print()
    print("=" * 70)
    print("讀取房價資料")
    print("=" * 70)

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
    ) as csvfile:

        reader = csv.DictReader(csvfile)

        fieldnames = reader.fieldnames or []

        print(
            f"資料欄位數：{len(fieldnames)}"
        )

        print()
        print("必要欄位檢查：")

        required_fields = [
            "case_t",
            "district",
            "uprice",
            "price",
            "farea",
            "buitype",
            "location",
        ]

        all_ok = True

        for field in required_fields:

            if field in fieldnames:

                print(
                    f"  ✓ {field}"
                )

            else:

                print(
                    f"  ✗ {field}"
                )

                all_ok = False

        # price 不存在時，嘗試 tprice
        if "price" not in fieldnames:

            if "tprice" in fieldnames:

                print()
                print(
                    "⚠️ 找不到 price，但找到 tprice。"
                )

                print(
                    "系統將使用 tprice 作為總價。"
                )

            else:

                print()
                print(
                    "錯誤：CSV 缺少必要總價欄位。"
                )

                return []

        if "uprice" not in fieldnames:

            print()
            print(
                "錯誤：CSV 缺少 uprice。"
            )

            return []

        for row in reader:

            district = str(
                row.get("district", "")
            ).strip()

            if district not in TARGET_DISTRICTS:
                continue

            records.append(row)

    print()
    print(
        f"讀取到士林區／北投區資料："
        f"{len(records):,} 筆"
    )

    return records


# ============================================================
# 資料品質檢查
# ============================================================

def check_data_quality(records, district):

    district_records = [
        row
        for row in records
        if str(
            row.get("district", "")
        ).strip() == district
    ]

    sale_records = [
        row
        for row in district_records
        if str(
            row.get("case_t", "")
        ).strip() == "買賣"
    ]

    valid_items = []

    no_area = 0
    no_unit_price = 0
    no_total_price = 0

    for row in sale_records:

        unit_price = to_float(
            row.get("uprice")
        )

        total_value = row.get("price")

        if total_value in (None, ""):
            total_value = row.get("tprice")

        total_price = to_float(
            total_value
        )

        area = to_float(
            row.get("farea")
        )

        if area is None or area <= 0:
            no_area += 1
            continue

        if unit_price is None or unit_price <= 0:
            no_unit_price += 1
            continue

        if total_price is None or total_price <= 0:
            no_total_price += 1
            continue

        valid_items.append({
            "row": row,
            "unit_price": unit_price,
            "total_price": total_price,
            "area": area,
        })

    excluded = (
        len(sale_records)
        - len(valid_items)
    )

    print()
    print(
        f"{district} 【資料品質檢查】"
    )

    print(
        f"原始符合行政區／買賣資料："
        f"{len(sale_records):,} 筆"
    )

    print(
        f"有效住宅交易："
        f"{len(valid_items):,} 筆"
    )

    print(
        f"品質排除："
        f"{excluded:,} 筆"
    )

    if no_area:
        print(
            f"  └─ 無有效建物面積："
            f"{no_area:,} 筆"
        )

    if no_unit_price:
        print(
            f"  └─ 無有效單價："
            f"{no_unit_price:,} 筆"
        )

    if no_total_price:
        print(
            f"  └─ 無有效總價："
            f"{no_total_price:,} 筆"
        )

    return valid_items


# ============================================================
# 準備行政區資料
# ============================================================

def prepare_district_records(records, district):

    return check_data_quality(
        records,
        district
    )


# ============================================================
# 四分位數
# ============================================================

def percentile(values, percent):

    if not values:
        return None

    data = sorted(values)

    if len(data) == 1:
        return data[0]

    index = (
        (len(data) - 1)
        * percent
    )

    lower = int(index)

    upper = lower + 1

    if upper >= len(data):
        return data[lower]

    weight = index - lower

    return (
        data[lower]
        * (1 - weight)
        + data[upper]
        * weight
    )


# ============================================================
# 統計計算
# ============================================================

def calculate_stats(items):

    unit_prices = [
        item["unit_price"]
        for item in items
    ]

    total_prices = [
        item["total_price"]
        for item in items
    ]

    areas = [
        item["area"]
        for item in items
    ]

    q1 = percentile(
        unit_prices,
        0.25
    )

    q3 = percentile(
        unit_prices,
        0.75
    )

    iqr = None

    lower = None
    upper = None

    if q1 is not None and q3 is not None:

        iqr = q3 - q1

        lower = q1 - 1.5 * iqr

        upper = q3 + 1.5 * iqr

    normal_items = []
    abnormal_items = []

    for item in items:

        price = item["unit_price"]

        if (
            lower is not None
            and upper is not None
            and (
                price < lower
                or price > upper
            )
        ):

            abnormal_items.append(item)

        else:

            normal_items.append(item)

    normal_prices = [
        item["unit_price"]
        for item in normal_items
    ]

    normal_totals = [
        item["total_price"]
        for item in normal_items
    ]

    normal_areas = [
        item["area"]
        for item in normal_items
    ]

    stats = {
        "count": len(items),

        "average_price":
            mean(unit_prices),

        "median_price":
            median(unit_prices),

        "max_price":
            max(unit_prices),

        "min_price":
            min(unit_prices),

        "average_total":
            mean(total_prices),

        "average_area":
            mean(areas),

        "q1": q1,
        "q3": q3,

        "iqr_lower": lower,
        "iqr_upper": upper,

        "normal_count":
            len(normal_items),

        "abnormal_count":
            len(abnormal_items),

        "abnormal_items":
            abnormal_items,

        "normal_average_price":
            mean(normal_prices)
            if normal_prices
            else None,

        "normal_median_price":
            median(normal_prices)
            if normal_prices
            else None,

        "normal_average_total":
            mean(normal_totals)
            if normal_totals
            else None,

        "normal_average_area":
            mean(normal_areas)
            if normal_areas
            else None,
    }

    return stats


# ============================================================
# 住宅類型分析
# ============================================================

def analyze_building_types(items):

    groups = defaultdict(list)

    for item in items:

        building_type = normalize_building_type(
            item["row"]
        )

        groups[building_type].append(
            item
        )

    print()
    print("住宅類型行情：")

    sorted_groups = sorted(
        groups.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    for building_type, group in sorted_groups:

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {building_type}："
            f"{len(group):,} 筆"
            f"｜平均 "
            f"{mean(prices):,.2f} 萬/坪"
            f"｜中位數 "
            f"{median(prices):,.2f} 萬/坪"
        )


# ============================================================
# 價格區間
# ============================================================

def analyze_price_ranges(items):

    ranges = {
        "50萬以下": 0,
        "50～70萬": 0,
        "70～90萬": 0,
        "90～120萬": 0,
        "120萬以上": 0,
    }

    for item in items:

        price = item["unit_price"]

        if price < 50:

            ranges["50萬以下"] += 1

        elif price < 70:

            ranges["50～70萬"] += 1

        elif price < 90:

            ranges["70～90萬"] += 1

        elif price < 120:

            ranges["90～120萬"] += 1

        else:

            ranges["120萬以上"] += 1

    print()
    print("單價區間分布：")

    for label, count in ranges.items():

        print(
            f"  {label}：{count:,} 筆"
        )


# ============================================================
# 異常交易
# ============================================================

def show_abnormal_cases(stats):

    abnormal = stats["abnormal_items"]

    print()
    print(
        f"⚠️ IQR 異常交易候選："
        f"{len(abnormal):,} 筆"
    )

    if not abnormal:

        print(
            "沒有偵測到明顯異常價格。"
        )

        return

    highest = sorted(
        abnormal,
        key=lambda x: x["unit_price"],
        reverse=True
    )[:5]

    high_count = len(highest)

    print()
    print(
        f"🔴 高價異常候選："
        f"{high_count:,} 筆"
    )

    for item in highest:

        row = item["row"]

        print(
            f"  {item['unit_price']:,.2f} 萬/坪"
            f"｜{row.get('location', '無資料')}"
            f"｜總價 "
            f"{item['total_price']:,.2f} 萬"
            f"｜面積 "
            f"{item['area']:,.2f} 坪"
        )

    lowest = sorted(
        abnormal,
        key=lambda x: x["unit_price"]
    )[:5]

    lower_bound = stats.get(
        "iqr_lower"
    )

    low_items = []

    if lower_bound is not None:

        low_items = [
            item
            for item in abnormal
            if item["unit_price"]
            < lower_bound
        ]

    print()
    print(
        f"🔵 低價異常候選："
        f"{len(low_items):,} 筆"
    )

    if not low_items:

        print(
            "  沒有低於 IQR 合理下限的低價異常交易。"
        )

    else:

        for item in low_items[:5]:

            row = item["row"]

            print(
                f"  {item['unit_price']:,.2f} 萬/坪"
                f"｜{row.get('location', '無資料')}"
                f"｜總價 "
                f"{item['total_price']:,.2f} 萬"
            )


# ============================================================
# 路段分析
# ============================================================

def analyze_routes(items):

    groups = defaultdict(list)

    for item in items:

        route = extract_route(
            item["row"].get(
                "location",
                ""
            )
        )

        groups[route].append(
            item
        )

    valid_groups = {
        route: group
        for route, group in groups.items()
        if len(group) >= MIN_ROUTE_TRANSACTIONS
    }

    print()
    print("【六、路段行情分析】")

    print(
        f"可分析路段："
        f"{len(valid_groups):,} 條"
    )

    if not valid_groups:

        print(
            "目前沒有足夠交易量的路段。"
        )

        return valid_groups

    # --------------------------------------------------------
    # 平均單價
    # --------------------------------------------------------

    route_price = []

    for route, group in valid_groups.items():

        prices = [
            item["unit_price"]
            for item in group
        ]

        route_price.append(
            (
                route,
                len(group),
                mean(prices),
                median(prices)
            )
        )

    route_price.sort(
        key=lambda x: x[2],
        reverse=True
    )

    print()
    print("🏆 路段平均單價排行榜：")

    for index, data in enumerate(
        route_price[:10],
        start=1
    ):

        route, count, avg, med = data

        print(
            f"  {index}. "
            f"{route}｜"
            f"{count} 筆｜"
            f"平均 {avg:,.2f} 萬/坪｜"
            f"中位數 {med:,.2f} 萬/坪"
        )

    # --------------------------------------------------------
    # 交易量
    # --------------------------------------------------------

    route_count = sorted(
        valid_groups.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    print()
    print("📊 路段交易量排行榜：")

    for index, (
        route,
        group
    ) in enumerate(
        route_count[:10],
        start=1
    ):

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {index}. "
            f"{route}｜"
            f"交易 {len(group)} 筆｜"
            f"平均 {mean(prices):,.2f} 萬/坪"
        )

    # --------------------------------------------------------
    # 熱度
    # --------------------------------------------------------

    print()
    print("🔥 路段市場熱度排行榜：")

    heat_data = []

    for route, group in valid_groups.items():

        prices = [
            item["unit_price"]
            for item in group
        ]

        avg = mean(prices)

        heat = (
            len(group)
            * avg
        )

        heat_data.append(
            (
                route,
                len(group),
                avg,
                heat
            )
        )

    heat_data.sort(
        key=lambda x: x[3],
        reverse=True
    )

    for index, data in enumerate(
        heat_data[:10],
        start=1
    ):

        route, count, avg, heat = data

        print(
            f"  {index}. "
            f"{route}｜"
            f"交易 {count} 筆｜"
            f"均價 {avg:,.2f} 萬/坪｜"
            f"熱度 {heat:,.2f}"
        )

    return valid_groups


# ============================================================
# 路段＋住宅類型
# ============================================================

def analyze_route_building_types(items):

    groups = defaultdict(list)

    for item in items:

        route = extract_route(
            item["row"].get(
                "location",
                ""
            )
        )

        building_type = normalize_building_type(
            item["row"]
        )

        key = (
            route,
            building_type
        )

        groups[key].append(
            item
        )

    valid = [
        (
            route,
            building_type,
            group
        )
        for (
            route,
            building_type
        ), group in groups.items()
        if len(group) >= 2
    ]

    valid.sort(
        key=lambda x: mean(
            [
                item["unit_price"]
                for item in x[2]
            ]
        ),
        reverse=True
    )

    print()
    print(
        "【七、路段＋住宅類型交叉分析】"
    )

    print(
        f"僅顯示至少 2 筆交易的組別："
        f"{len(valid):,} 組"
    )

    for index, (
        route,
        building_type,
        group
    ) in enumerate(
        valid[:10],
        start=1
    ):

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {index}. "
            f"{route}｜"
            f"{building_type}｜"
            f"{len(group)} 筆｜"
            f"平均 {mean(prices):,.2f} 萬/坪｜"
            f"中位數 {median(prices):,.2f} 萬/坪"
        )


# ============================================================
# 市場熱點摘要
# ============================================================

def print_market_summary(items):

    groups = defaultdict(list)

    for item in items:

        route = extract_route(
            item["row"].get(
                "location",
                ""
            )
        )

        groups[route].append(
            item
        )

    valid = [
        (
            route,
            group
        )
        for route, group in groups.items()
        if len(group) >= 2
    ]

    if not valid:

        return

    heat_data = []

    for route, group in valid:

        avg = mean(
            [
                item["unit_price"]
                for item in group
            ]
        )

        heat = (
            len(group)
            * avg
        )

        heat_data.append(
            (
                route,
                len(group),
                avg,
                heat
            )
        )

    heat_data.sort(
        key=lambda x: x[3],
        reverse=True
    )

    print()
    print("【八、市場熱點摘要】")

    hottest = heat_data[0]

    highest_price = max(
        heat_data,
        key=lambda x: x[2]
    )

    highest_count = max(
        heat_data,
        key=lambda x: x[1]
    )

    print()
    print("🔥 市場熱度最高路段：")

    print(
        f"  {hottest[0]}｜"
        f"交易 {hottest[1]} 筆｜"
        f"平均 {hottest[2]:,.2f} 萬/坪"
    )

    print()
    print("💰 平均單價最高路段：")

    print(
        f"  {highest_price[0]}｜"
        f"交易 {highest_price[1]} 筆｜"
        f"平均 {highest_price[2]:,.2f} 萬/坪"
    )

    print()
    print("📊 交易量最高路段：")

    print(
        f"  {highest_count[0]}｜"
        f"交易 {highest_count[1]} 筆｜"
        f"平均 {highest_count[2]:,.2f} 萬/坪"
    )


# ============================================================
# 歷史月份分析
# ============================================================

def build_month_groups(items):

    groups = defaultdict(list)

    for item in items:

        row = item["row"]

        date_value = get_transaction_date(
            row
        )

        month = date_to_month(
            date_value
        )

        if month:

            groups[month].append(
                item
            )

    return groups


def trend_direction(change_percent):

    if change_percent is None:
        return "資料不足"

    if change_percent >= 3:
        return "上升"

    if change_percent <= -3:
        return "下降"

    return "盤整"


def analyze_monthly_trend(items, district):

    print()
    print("【九、歷史價格趨勢分析】")

    month_groups = build_month_groups(
        items
    )

    if not month_groups:

        print(
            "⚠️ 找不到可解析的交易日期。"
        )

        print(
            "系統已嘗試 fdate、sdate、"
            "transaction_date、trade_date、date、_importdate。"
        )

        return None

    months = sorted(
        month_groups.keys()
    )

    print()
    print(
        f"可分析月份："
        f"{len(months):,} 個"
    )

    monthly_data = []

    for month in months:

        group = month_groups[month]

        prices = [
            item["unit_price"]
            for item in group
        ]

        monthly_data.append({
            "month": month,
            "count": len(group),
            "average": mean(prices),
            "median": median(prices),
        })

    print()
    print(
        f"{'月份':<12}"
        f"{'交易量':>8}"
        f"{'平均單價':>14}"
        f"{'中位數':>14}"
        f"{'月增率':>12}"
        f"{'方向':>8}"
    )

    print("-" * 72)

    previous = None

    for data in monthly_data:

        change = None

        if (
            previous
            and previous["average"] != 0
        ):

            change = (
                (
                    data["average"]
                    - previous["average"]
                )
                / previous["average"]
                * 100
            )

        direction = trend_direction(
            change
        )

        change_text = (
            f"{change:+.2f}%"
            if change is not None
            else "—"
        )

        print(
            f"{data['month']:<12}"
            f"{data['count']:>8,}"
            f"{data['average']:>14,.2f}"
            f"{data['median']:>14,.2f}"
            f"{change_text:>12}"
            f"{direction:>8}"
        )

        previous = data

    # --------------------------------------------------------
    # 整體趨勢
    # --------------------------------------------------------

    print()
    print("📈 市場方向判斷：")

    if len(monthly_data) >= 2:

        first = monthly_data[0]
        last = monthly_data[-1]

        total_change = (
            (
                last["average"]
                - first["average"]
            )
            / first["average"]
            * 100
        )

        direction = trend_direction(
            total_change
        )

        print(
            f"  {district}："
            f"{direction}"
        )

        print(
            f"  最早月份："
            f"{first['month']} "
            f"{first['average']:,.2f} 萬/坪"
        )

        print(
            f"  最新月份："
            f"{last['month']} "
            f"{last['average']:,.2f} 萬/坪"
        )

        print(
            f"  期間變化："
            f"{total_change:+.2f}%"
        )

    else:

        print(
            "  資料不足，至少需要 2 個月份。"
        )

    return monthly_data


# ============================================================
# 路段歷史趨勢
# ============================================================

def analyze_route_history(items):

    print()
    print("【十、路段歷史價格趨勢】")

    route_month_groups = defaultdict(
        lambda: defaultdict(list)
    )

    for item in items:

        row = item["row"]

        date_value = get_transaction_date(
            row
        )

        month = date_to_month(
            date_value
        )

        if not month:
            continue

        route = extract_route(
            row.get(
                "location",
                ""
            )
        )

        route_month_groups[
            route
        ][month].append(
            item["unit_price"]
        )

    route_results = []

    for route, month_groups in route_month_groups.items():

        months = sorted(
            month_groups.keys()
        )

        if len(months) < 2:
            continue

        first_month = months[0]
        last_month = months[-1]

        first_prices = month_groups[
            first_month
        ]

        last_prices = month_groups[
            last_month
        ]

        first_avg = mean(
            first_prices
        )

        last_avg = mean(
            last_prices
        )

        if first_avg == 0:
            continue

        change = (
            (
                last_avg
                - first_avg
            )
            / first_avg
            * 100
        )

        total_count = sum(
            len(values)
            for values in month_groups.values()
        )

        if total_count < MIN_ROUTE_TRANSACTIONS:
            continue

        route_results.append({
            "route": route,
            "count": total_count,
            "first_month": first_month,
            "last_month": last_month,
            "first_avg": first_avg,
            "last_avg": last_avg,
            "change": change,
            "direction":
                trend_direction(change),
        })

    if not route_results:

        print(
            "目前沒有足夠歷史資料的路段。"
        )

        return

    # 最強上升
    rising = sorted(
        route_results,
        key=lambda x: x["change"],
        reverse=True
    )

    print()
    print("📈 路段上升排行榜：")

    for index, item in enumerate(
        rising[:10],
        start=1
    ):

        if item["change"] <= 0:
            break

        print(
            f"  {index}. "
            f"{item['route']}｜"
            f"{item['first_month']} → "
            f"{item['last_month']}｜"
            f"{item['first_avg']:,.2f} → "
            f"{item['last_avg']:,.2f} 萬/坪｜"
            f"{item['change']:+.2f}%"
        )

    # 最大下降
    falling = sorted(
        route_results,
        key=lambda x: x["change"]
    )

    print()
    print("📉 路段下降排行榜：")

    found_falling = False

    for index, item in enumerate(
        falling[:10],
        start=1
    ):

        if item["change"] >= 0:
            continue

        found_falling = True

        print(
            f"  {index}. "
            f"{item['route']}｜"
            f"{item['first_month']} → "
            f"{item['last_month']}｜"
            f"{item['first_avg']:,.2f} → "
            f"{item['last_avg']:,.2f} 萬/坪｜"
            f"{item['change']:+.2f}%"
        )

    if not found_falling:

        print(
            "  目前沒有明顯下降路段。"
        )


# ============================================================
# 士林／北投歷史比較
# ============================================================

def compare_historical_trends(
    district_items
):

    print()
    print("【十一、士林區 vs 北投區歷史趨勢】")

    district_month_data = {}

    for district, items in district_items.items():

        month_groups = build_month_groups(
            items
        )

        data = {}

        for month, group in month_groups.items():

            prices = [
                item["unit_price"]
                for item in group
            ]

            data[month] = {
                "count": len(group),
                "average": mean(prices),
                "median": median(prices),
            }

        district_month_data[
            district
        ] = data

    all_months = set()

    for data in district_month_data.values():

        all_months.update(
            data.keys()
        )

    months = sorted(
        all_months
    )

    if not months:

        print(
            "沒有可比較的歷史月份。"
        )

        return

    print()

    print(
        f"{'月份':<12}"
        f"{'士林區':>16}"
        f"{'北投區':>16}"
        f"{'價差':>16}"
    )

    print("-" * 62)

    for month in months:

        shilin = district_month_data.get(
            "士林區",
            {}
        ).get(month)

        beitou = district_month_data.get(
            "北投區",
            {}
        ).get(month)

        shilin_text = (
            f"{shilin['average']:,.2f}"
            if shilin
            else "—"
        )

        beitou_text = (
            f"{beitou['average']:,.2f}"
            if beitou
            else "—"
        )

        if shilin and beitou:

            difference = (
                shilin["average"]
                - beitou["average"]
            )

            difference_text = (
                f"{difference:+,.2f}"
            )

        else:

            difference_text = "—"

        print(
            f"{month:<12}"
            f"{shilin_text:>16}"
            f"{beitou_text:>16}"
            f"{difference_text:>16}"
        )


# ============================================================
# 行政區完整報告
# ============================================================

def print_district_report(
    district,
    items
):

    print()
    print("=" * 70)
    print(
        f"{district} 第八階段專業房價分析"
    )
    print("=" * 70)

    if not items:

        print(
            "沒有可分析的住宅買賣資料。"
        )

        return None

    stats = calculate_stats(
        items
    )

    # --------------------------------------------------------
    # 原始行情
    # --------------------------------------------------------

    print()
    print("【一、原始交易行情】")

    print(
        f"有效住宅買賣："
        f"{stats['count']:,} 筆"
    )

    print(
        f"平均單價："
        f"{stats['average_price']:,.2f} 萬/坪"
    )

    print(
        f"中位數單價："
        f"{stats['median_price']:,.2f} 萬/坪"
    )

    print(
        f"最高單價："
        f"{stats['max_price']:,.2f} 萬/坪"
    )

    print(
        f"最低單價："
        f"{stats['min_price']:,.2f} 萬/坪"
    )

    print(
        f"平均總價："
        f"{stats['average_total']:,.2f} 萬"
    )

    print(
        f"平均建物面積："
        f"{stats['average_area']:,.2f} 坪"
    )

    # --------------------------------------------------------
    # IQR
    # --------------------------------------------------------

    print()
    print("【二、主流行情／異常值分析】")

    print(
        f"Q1："
        f"{stats['q1']:,.2f} 萬/坪"
    )

    print(
        f"Q3："
        f"{stats['q3']:,.2f} 萬/坪"
    )

    if stats["iqr_lower"] is not None:

        print(
            f"IQR 合理下限："
            f"{stats['iqr_lower']:,.2f} 萬/坪"
        )

        print(
            f"IQR 合理上限："
            f"{stats['iqr_upper']:,.2f} 萬/坪"
        )

    print(
        f"主流交易："
        f"{stats['normal_count']:,} 筆"
    )

    print(
        f"異常交易候選："
        f"{stats['abnormal_count']:,} 筆"
    )

    if stats["normal_average_price"] is not None:

        print(
            f"主流平均單價："
            f"{stats['normal_average_price']:,.2f} 萬/坪"
        )

        print(
            f"主流中位數單價："
            f"{stats['normal_median_price']:,.2f} 萬/坪"
        )

        print(
            f"主流平均總價："
            f"{stats['normal_average_total']:,.2f} 萬"
        )

        print(
            f"主流平均面積："
            f"{stats['normal_average_area']:,.2f} 坪"
        )

    # --------------------------------------------------------
    # 住宅類型
    # --------------------------------------------------------

    print()
    print("【三、住宅類型】")

    analyze_building_types(
        items
    )

    # --------------------------------------------------------
    # 價格區間
    # --------------------------------------------------------

    print()
    print("【四、單價區間】")

    analyze_price_ranges(
        items
    )

    # --------------------------------------------------------
    # 異常交易
    # --------------------------------------------------------

    print()
    print("【五、異常交易候選】")

    show_abnormal_cases(
        stats
    )

    # --------------------------------------------------------
    # 最高單價
    # --------------------------------------------------------

    highest = max(
        items,
        key=lambda x: x["unit_price"]
    )

    highest_row = highest["row"]

    print()
    print("【最高單價案例】")

    print(
        f"單價："
        f"{highest['unit_price']:,.2f} 萬/坪"
    )

    print(
        f"地址："
        f"{highest_row.get('location', '無資料')}"
    )

    print(
        f"總價："
        f"{highest['total_price']:,.2f} 萬"
    )

    print(
        f"面積："
        f"{highest['area']:,.2f} 坪"
    )

    # --------------------------------------------------------
    # 最低單價
    # --------------------------------------------------------

    lowest = min(
        items,
        key=lambda x: x["unit_price"]
    )

    lowest_row = lowest["row"]

    print()
    print("【最低單價案例】")

    print(
        f"單價："
        f"{lowest['unit_price']:,.2f} 萬/坪"
    )

    print(
        f"地址："
        f"{lowest_row.get('location', '無資料')}"
    )

    print(
        f"總價："
        f"{lowest['total_price']:,.2f} 萬"
    )

    print(
        f"面積："
        f"{lowest['area']:,.2f} 坪"
    )

    # --------------------------------------------------------
    # 路段
    # --------------------------------------------------------

    analyze_routes(
        items
    )

    # --------------------------------------------------------
    # 路段＋住宅類型
    # --------------------------------------------------------

    analyze_route_building_types(
        items
    )

    # --------------------------------------------------------
    # 市場熱點
    # --------------------------------------------------------

    print_market_summary(
        items
    )

    # --------------------------------------------------------
    # 歷史趨勢
    # --------------------------------------------------------

    analyze_monthly_trend(
        items,
        district
    )

    # --------------------------------------------------------
    # 路段歷史
    # --------------------------------------------------------

    analyze_route_history(
        items
    )

    print()
    print("=" * 70)

    return stats


# ============================================================
# 士林／北投比較
# ============================================================

def compare_districts(
    stats_map
):

    shilin = stats_map.get(
        "士林區"
    )

    beitou = stats_map.get(
        "北投區"
    )

    if not shilin or not beitou:

        print()
        print(
            "無法進行士林區／北投區比較。"
        )

        return

    print()
    print("=" * 70)
    print(
        "士林區 vs 北投區 房價比較"
    )
    print("=" * 70)

    print()

    print(
        f"{'項目':<18}"
        f"{'士林區':>15}"
        f"{'北投區':>15}"
    )

    print("-" * 50)

    print(
        f"{'有效交易':<18}"
        f"{shilin['count']:>15,}"
        f"{beitou['count']:>15,}"
    )

    print(
        f"{'平均單價':<18}"
        f"{shilin['average_price']:>15,.2f}"
        f"{beitou['average_price']:>15,.2f}"
    )

    print(
        f"{'中位數單價':<18}"
        f"{shilin['median_price']:>15,.2f}"
        f"{beitou['median_price']:>15,.2f}"
    )

    print(
        f"{'主流平均單價':<18}"
        f"{shilin['normal_average_price']:>15,.2f}"
        f"{beitou['normal_average_price']:>15,.2f}"
    )

    print(
        f"{'平均總價':<18}"
        f"{shilin['average_total']:>15,.2f}"
        f"{beitou['average_total']:>15,.2f}"
    )

    print(
        f"{'平均面積':<18}"
        f"{shilin['average_area']:>15,.2f}"
        f"{beitou['average_area']:>15,.2f}"
    )

    price_difference = (
        shilin["normal_average_price"]
        - beitou["normal_average_price"]
    )

    if (
        beitou["normal_average_price"]
        != 0
    ):

        percentage = (
            price_difference
            / beitou["normal_average_price"]
            * 100
        )

    else:

        percentage = 0

    print()
    print("【市場價格差異】")

    if price_difference > 0:

        print(
            f"士林區主流平均單價"
            f"比北投區高 "
            f"{price_difference:,.2f} 萬/坪"
        )

        print(
            f"約高 {percentage:,.2f}%"
        )

    elif price_difference < 0:

        print(
            f"北投區主流平均單價"
            f"比士林區高 "
            f"{abs(price_difference):,.2f} 萬/坪"
        )

        print(
            f"約高 {abs(percentage):,.2f}%"
        )

    else:

        print(
            "兩區主流平均單價接近。"
        )

    print()
    print("=" * 70)


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "台北市士林區／北投區房市監控系統"
    )
    print(
        "第八階段：歷史價格趨勢＋路段＋住宅類型＋市場熱點分析"
    )
    print("=" * 70)

    records = load_data()

    if not records:

        print()
        print(
            "目前沒有可以分析的資料。"
        )

        return

    stats_map = {}

    district_items = {}

    # --------------------------------------------------------
    # 分析兩區
    # --------------------------------------------------------

    for district in sorted(
        TARGET_DISTRICTS
    ):

        items = prepare_district_records(
            records,
            district
        )

        district_items[
            district
        ] = items

        stats = print_district_report(
            district,
            items
        )

        if stats:

            stats_map[
                district
            ] = stats

    # --------------------------------------------------------
    # 士林／北投比較
    # --------------------------------------------------------

    compare_districts(
        stats_map
    )

    # --------------------------------------------------------
    # 歷史比較
    # --------------------------------------------------------

    compare_historical_trends(
        district_items
    )

    # --------------------------------------------------------
    # 完成
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "第八階段房市分析完成"
    )
    print(
        "歷史趨勢、路段趨勢、"
        "住宅類型與市場熱點分析完成"
    )
    print("=" * 70)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
