# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統

第七階段：
路段行情＋住宅類型＋市場熱點分析

功能：
1. CSV 資料品質檢查
2. 住宅買賣交易篩選
3. 平均／中位數／最高／最低單價
4. 平均總價／平均建物面積
5. IQR 主流行情與異常交易
6. 住宅類型分析
7. 單價區間分析
8. 最高／最低單價案例
9. 路段行情分析
10. 路段交易量排行榜
11. 路段平均單價排行榜
12. 路段市場熱度分析
13. 路段＋住宅類型交叉分析
14. 士林區／北投區比較

重要資料欄位：
uprice = 交易單價（萬元／坪）
tprice = 交易總價（萬元）
farea  = 建物移轉總面積（坪）
pu_area = 共有部分面積
"""


import csv
import os
import re
from statistics import mean, median


# ============================================================
# 基本設定
# ============================================================

INPUT_FILE = "data/taipei_transactions.csv"

TARGET_DISTRICTS = {
    "士林區",
    "北投區",
}

REQUIRED_COLUMNS = [
    "case_t",
    "district",
    "uprice",
    "tprice",
    "farea",
    "buitype",
    "location",
]

TOP_ROUTE_COUNT = 15
TOP_CROSS_COUNT = 20


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

    try:
        return float(value)

    except (ValueError, TypeError):
        return None


# ============================================================
# 四捨五入顯示
# ============================================================

def safe_mean(values):

    if not values:
        return None

    return mean(values)


def safe_median(values):

    if not values:
        return None

    return median(values)


# ============================================================
# 百分位數
# ============================================================

def percentile(values, percent):

    if not values:
        return None

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * percent

    lower = int(position)
    upper = lower + 1

    if upper >= len(values):
        return values[lower]

    weight = position - lower

    return (
        values[lower]
        + (values[upper] - values[lower]) * weight
    )


# ============================================================
# 路段名稱整理
# ============================================================

def extract_route(location):

    """
    從地址中擷取主要道路名稱。

    例如：

    德行東路109巷3號一樓
        -> 德行東路

    天母西路
        -> 天母西路

    中山北路七段266巷
        -> 中山北路七段

    中央北路二段320巷
        -> 中央北路二段

    如果無法辨識，回傳「其他」。
    """

    if location is None:
        return "其他"

    text = str(location).strip()

    if not text:
        return "其他"

    # --------------------------------------------------------
    # 去除行政區前綴
    # --------------------------------------------------------

    text = text.replace("台北市", "")
    text = text.replace("臺北市", "")
    text = text.replace("士林區", "")
    text = text.replace("北投區", "")

    # --------------------------------------------------------
    # 優先找「路／街／大道」
    # --------------------------------------------------------

    pattern = (
        r"(.+?"
        r"(?:大道|路|街)"
        r"(?:"
        r"[一二三四五六七八九十百]+段"
        r"|[0-9]+段"
        r")?"
        r")"
    )

    match = re.search(pattern, text)

    if match:

        route = match.group(1).strip()

        if route:
            return route

    # --------------------------------------------------------
    # 如果沒有路／街，嘗試巷
    # --------------------------------------------------------

    match = re.search(
        r"(.+?巷)",
        text
    )

    if match:

        route = match.group(1).strip()

        if route:
            return route

    return "其他"


# ============================================================
# 住宅類型標準化
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

        print()
        print(f"錯誤：找不到資料檔案：{INPUT_FILE}")
        return []

    records = []

    try:

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

            for column in REQUIRED_COLUMNS:

                if column in fieldnames:

                    print(
                        f"  ✓ {column}"
                    )

                else:

                    print(
                        f"  ✗ {column}"
                    )

            missing = [
                column
                for column in REQUIRED_COLUMNS
                if column not in fieldnames
            ]

            if missing:

                print()
                print(
                    "錯誤：CSV 缺少必要欄位："
                )

                for column in missing:
                    print(f"  {column}")

                return []

            print()
            print("資料欄位：")
            print(", ".join(fieldnames))

            for row in reader:

                district = str(
                    row.get("district", "")
                ).strip()

                if district not in TARGET_DISTRICTS:
                    continue

                records.append(row)

    except Exception as error:

        print()
        print(
            f"讀取 CSV 發生錯誤：{error}"
        )

        return []

    print()
    print(
        f"讀取到士林區／北投區資料："
        f"{len(records):,} 筆"
    )

    return records


# ============================================================
# 準備單一行政區交易資料
# ============================================================

def prepare_district_records(records, district):

    raw_count = 0
    valid_count = 0

    no_area_count = 0
    no_unit_price_count = 0
    no_total_price_count = 0

    items = []

    for row in records:

        row_district = str(
            row.get("district", "")
        ).strip()

        if row_district != district:
            continue

        case_type = str(
            row.get("case_t", "")
        ).strip()

        if case_type != "買賣":
            continue

        raw_count += 1

        # ----------------------------------------------------
        # 單價
        # ----------------------------------------------------

        unit_price = to_float(
            row.get("uprice")
        )

        if unit_price is None or unit_price <= 0:

            no_unit_price_count += 1
            continue

        # ----------------------------------------------------
        # 總價
        # 使用 tprice
        # ----------------------------------------------------

        total_price = to_float(
            row.get("tprice")
        )

        if total_price is None or total_price <= 0:

            no_total_price_count += 1
            continue

        # ----------------------------------------------------
        # 建物面積
        # ----------------------------------------------------

        area = to_float(
            row.get("farea")
        )

        if area is None or area <= 0:

            no_area_count += 1
            continue

        # ----------------------------------------------------
        # 路段
        # ----------------------------------------------------

        location = str(
            row.get("location", "")
        ).strip()

        route = extract_route(
            location
        )

        building_type = normalize_building_type(
            row
        )

        items.append({

            "row": row,

            "unit_price": unit_price,

            "total_price": total_price,

            "area": area,

            "route": route,

            "building_type": building_type,

        })

        valid_count += 1

    # --------------------------------------------------------
    # 資料品質報告
    # --------------------------------------------------------

    print()
    print(
        f"{district} 【資料品質檢查】"
    )

    print(
        f"原始符合行政區／買賣資料："
        f"{raw_count:,} 筆"
    )

    print(
        f"有效住宅交易："
        f"{valid_count:,} 筆"
    )

    quality_excluded = (
        no_area_count
        + no_unit_price_count
        + no_total_price_count
    )

    print(
        f"品質排除："
        f"{quality_excluded:,} 筆"
    )

    if no_area_count:

        print(
            f"  └─ 無有效建物面積："
            f"{no_area_count:,} 筆"
        )

    if no_unit_price_count:

        print(
            f"  └─ 無有效單價："
            f"{no_unit_price_count:,} 筆"
        )

    if no_total_price_count:

        print(
            f"  └─ 無有效總價："
            f"{no_total_price_count:,} 筆"
        )

    return items


# ============================================================
# 計算 IQR
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

    if q1 is not None and q3 is not None:

        iqr = q3 - q1

        iqr_lower = q1 - 1.5 * iqr

        iqr_upper = q3 + 1.5 * iqr

    else:

        iqr_lower = None
        iqr_upper = None

    # --------------------------------------------------------
    # 主流交易
    # --------------------------------------------------------

    if (
        iqr_lower is not None
        and iqr_upper is not None
    ):

        normal_items = [

            item

            for item in items

            if (
                item["unit_price"]
                >= iqr_lower
                and
                item["unit_price"]
                <= iqr_upper
            )
        ]

        abnormal_items = [

            item

            for item in items

            if (
                item["unit_price"]
                < iqr_lower
                or
                item["unit_price"]
                > iqr_upper
            )
        ]

    else:

        normal_items = list(items)

        abnormal_items = []

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

    return {

        "count": len(items),

        "average_price": mean(unit_prices),

        "median_price": median(unit_prices),

        "max_price": max(unit_prices),

        "min_price": min(unit_prices),

        "average_total": mean(total_prices),

        "average_area": mean(areas),

        "q1": q1,

        "q3": q3,

        "iqr_lower": iqr_lower,

        "iqr_upper": iqr_upper,

        "normal_count": len(normal_items),

        "abnormal_count": len(abnormal_items),

        "abnormal_items": abnormal_items,

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


# ============================================================
# 住宅類型分析
# ============================================================

def analyze_building_types(items):

    groups = {}

    for item in items:

        building_type = item[
            "building_type"
        ]

        if building_type not in groups:

            groups[building_type] = []

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
            f"  {building_type}"
            f"｜{len(group):,} 筆"
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

        "50萬以下": [],

        "50～70萬": [],

        "70～90萬": [],

        "90～120萬": [],

        "120萬以上": [],

    }

    for item in items:

        price = item["unit_price"]

        if price < 50:

            ranges["50萬以下"].append(
                item
            )

        elif price < 70:

            ranges["50～70萬"].append(
                item
            )

        elif price < 90:

            ranges["70～90萬"].append(
                item
            )

        elif price < 120:

            ranges["90～120萬"].append(
                item
            )

        else:

            ranges["120萬以上"].append(
                item
            )

    print()
    print("單價區間分布：")

    for label, group in ranges.items():

        print(
            f"  {label}："
            f"{len(group):,} 筆"
        )


# ============================================================
# 異常交易
# ============================================================

def show_abnormal_cases(stats):

    abnormal = stats[
        "abnormal_items"
    ]

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

    print()
    print(
        f"🔴 高價異常候選："
        f"{len(highest):,} 筆"
    )

    for item in highest:

        row = item["row"]

        print(
            f"  {item['unit_price']:,.2f}"
            f" 萬/坪"
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

    print()
    print(
        f"🔵 低價異常候選："
        f"{len(lowest):,} 筆"
    )

    low_items = [
        item
        for item in lowest
        if (
            stats["iqr_lower"] is not None
            and
            item["unit_price"]
            < stats["iqr_lower"]
        )
    ]

    if not low_items:

        print(
            "  沒有低於 IQR 合理下限的交易。"
        )

    else:

        for item in low_items:

            row = item["row"]

            print(
                f"  {item['unit_price']:,.2f}"
                f" 萬/坪"
                f"｜{row.get('location', '無資料')}"
                f"｜總價 "
                f"{item['total_price']:,.2f} 萬"
            )


# ============================================================
# 路段行情分析
# ============================================================

def analyze_routes(items):

    groups = {}

    for item in items:

        route = item["route"]

        if route not in groups:

            groups[route] = []

        groups[route].append(
            item
        )

    # 排除只有 1 筆的路段
    valid_groups = {
        route: group
        for route, group in groups.items()
        if len(group) >= 2
    }

    print()
    print("【六、路段行情分析】")

    if not valid_groups:

        print(
            "目前沒有至少 2 筆交易的路段。"
        )

        return

    print(
        f"可分析路段："
        f"{len(valid_groups):,} 條"
    )

    # --------------------------------------------------------
    # 平均價格排名
    # --------------------------------------------------------

    price_ranking = sorted(
        valid_groups.items(),
        key=lambda x:
        mean(
            item["unit_price"]
            for item in x[1]
        ),
        reverse=True
    )

    print()
    print(
        "🏆 路段平均單價排行榜："
    )

    for index, (route, group) in enumerate(
        price_ranking[:TOP_ROUTE_COUNT],
        start=1
    ):

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {index:>2}. "
            f"{route}"
            f"｜{len(group):,} 筆"
            f"｜平均 "
            f"{mean(prices):,.2f} 萬/坪"
            f"｜中位數 "
            f"{median(prices):,.2f} 萬/坪"
        )

    # --------------------------------------------------------
    # 交易量排名
    # --------------------------------------------------------

    volume_ranking = sorted(
        valid_groups.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    print()
    print(
        "📊 路段交易量排行榜："
    )

    for index, (route, group) in enumerate(
        volume_ranking[:TOP_ROUTE_COUNT],
        start=1
    ):

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {index:>2}. "
            f"{route}"
            f"｜{len(group):,} 筆"
            f"｜平均 "
            f"{mean(prices):,.2f} 萬/坪"
        )

    # --------------------------------------------------------
    # 市場熱度
    #
    # 簡單以：
    # 交易量 × 平均單價
    #
    # 作為市場熱度指標。
    #
    # 注意：
    # 這不是金融市場的標準指標，
    # 是本系統提供的比較指標。
    # --------------------------------------------------------

    heat_ranking = sorted(
        valid_groups.items(),
        key=lambda x:
        len(x[1])
        *
        mean(
            item["unit_price"]
            for item in x[1]
        ),
        reverse=True
    )

    print()
    print(
        "🔥 路段市場熱度排行榜："
    )

    for index, (route, group) in enumerate(
        heat_ranking[:TOP_ROUTE_COUNT],
        start=1
    ):

        avg_price = mean(
            item["unit_price"]
            for item in group
        )

        heat_score = (
            len(group)
            * avg_price
        )

        print(
            f"  {index:>2}. "
            f"{route}"
            f"｜交易 {len(group):,} 筆"
            f"｜均價 {avg_price:,.2f} 萬/坪"
            f"｜熱度 {heat_score:,.2f}"
        )


# ============================================================
# 路段＋住宅類型
# ============================================================

def analyze_route_building_type(items):

    groups = {}

    for item in items:

        route = item["route"]

        building_type = item[
            "building_type"
        ]

        key = (
            route,
            building_type
        )

        if key not in groups:

            groups[key] = []

        groups[key].append(
            item
        )

    valid_groups = {

        key: group

        for key, group in groups.items()

        if len(group) >= 2
    }

    print()
    print(
        "【七、路段＋住宅類型交叉分析】"
    )

    if not valid_groups:

        print(
            "目前沒有至少 2 筆交易的交叉組別。"
        )

        return

    ranking = sorted(
        valid_groups.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    print(
        f"僅顯示至少 2 筆交易的組別："
        f"{len(ranking):,} 組"
    )

    for index, (
        (route, building_type),
        group
    ) in enumerate(
        ranking[:TOP_CROSS_COUNT],
        start=1
    ):

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {index:>2}. "
            f"{route}"
            f"｜{building_type}"
            f"｜{len(group):,} 筆"
            f"｜平均 "
            f"{mean(prices):,.2f} 萬/坪"
            f"｜中位數 "
            f"{median(prices):,.2f} 萬/坪"
        )


# ============================================================
# 最高／最低單價
# ============================================================

def show_extreme_cases(items):

    # --------------------------------------------------------
    # 最高
    # --------------------------------------------------------

    highest = max(
        items,
        key=lambda x:
        x["unit_price"]
    )

    highest_row = highest["row"]

    print()
    print(
        "【最高單價案例】"
    )

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
    # 最低
    # --------------------------------------------------------

    lowest = min(
        items,
        key=lambda x:
        x["unit_price"]
    )

    lowest_row = lowest["row"]

    print()
    print(
        "【最低單價案例】"
    )

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


# ============================================================
# 單一行政區完整報告
# ============================================================

def print_district_report(
    district,
    items
):

    print()
    print("=" * 70)
    print(
        f"{district} 第七階段專業房價分析"
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
    # 一、原始行情
    # --------------------------------------------------------

    print()
    print(
        "【一、原始交易行情】"
    )

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
    # 二、IQR
    # --------------------------------------------------------

    print()
    print(
        "【二、主流行情／異常值分析】"
    )

    print(
        f"Q1："
        f"{stats['q1']:,.2f} 萬/坪"
    )

    print(
        f"Q3："
        f"{stats['q3']:,.2f} 萬/坪"
    )

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
            f"{stats['normal_average_price']:,.2f}"
            f" 萬/坪"
        )

        print(
            f"主流中位數單價："
            f"{stats['normal_median_price']:,.2f}"
            f" 萬/坪"
        )

        print(
            f"主流平均總價："
            f"{stats['normal_average_total']:,.2f}"
            f" 萬"
        )

        print(
            f"主流平均面積："
            f"{stats['normal_average_area']:,.2f}"
            f" 坪"
        )

    # --------------------------------------------------------
    # 三、住宅類型
    # --------------------------------------------------------

    print()
    print(
        "【三、住宅類型】"
    )

    analyze_building_types(
        items
    )

    # --------------------------------------------------------
    # 四、單價區間
    # --------------------------------------------------------

    print()
    print(
        "【四、單價區間】"
    )

    analyze_price_ranges(
        items
    )

    # --------------------------------------------------------
    # 五、異常交易
    # --------------------------------------------------------

    print()
    print(
        "【五、異常交易候選】"
    )

    show_abnormal_cases(
        stats
    )

    # --------------------------------------------------------
    # 極端案例
    # --------------------------------------------------------

    show_extreme_cases(
        items
    )

    # --------------------------------------------------------
    # 六、路段
    # --------------------------------------------------------

    analyze_routes(
        items
    )

    # --------------------------------------------------------
    # 七、路段＋住宅類型
    # --------------------------------------------------------

    analyze_route_building_type(
        items
    )

    print()
    print("=" * 70)

    return stats


# ============================================================
# 士林／北投比較
# ============================================================

def compare_districts(stats_map):

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

    print(
        "-" * 50
    )

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

    # --------------------------------------------------------
    # 價差
    # --------------------------------------------------------

    shilin_price = (
        shilin["normal_average_price"]
    )

    beitou_price = (
        beitou["normal_average_price"]
    )

    if (
        shilin_price is None
        or beitou_price is None
        or beitou_price == 0
    ):

        percentage = 0

    else:

        percentage = (
            (
                shilin_price
                - beitou_price
            )
            / beitou_price
            * 100
        )

    price_difference = (
        shilin_price
        - beitou_price
    )

    print()
    print(
        "【市場價格差異】"
    )

    if price_difference > 0:

        print(
            f"士林區主流平均單價"
            f"比北投區高 "
            f"{price_difference:,.2f} 萬/坪"
        )

        print(
            f"約高 "
            f"{percentage:,.2f}%"
        )

    elif price_difference < 0:

        print(
            f"北投區主流平均單價"
            f"比士林區高 "
            f"{abs(price_difference):,.2f}"
            f" 萬/坪"
        )

        print(
            f"約高 "
            f"{abs(percentage):,.2f}%"
        )

    else:

        print(
            "兩區主流平均單價接近。"
        )

    print()
    print("=" * 70)


# ============================================================
# 市場熱點摘要
# ============================================================

def print_market_hotspot_summary(
    district_items
):

    print()
    print(
        "【八、市場熱點摘要】"
    )

    if not district_items:

        print(
            "沒有足夠資料。"
        )

        return

    route_groups = {}

    for item in district_items:

        route = item["route"]

        if route not in route_groups:

            route_groups[route] = []

        route_groups[route].append(
            item
        )

    valid = {

        route: group

        for route, group
        in route_groups.items()

        if len(group) >= 2
    }

    if not valid:

        print(
            "目前沒有足夠路段資料。"
        )

        return

    # --------------------------------------------------------
    # 最熱門
    # --------------------------------------------------------

    hottest_route = max(
        valid.items(),
        key=lambda x:
        len(x[1])
        *
        mean(
            item["unit_price"]
            for item in x[1]
        )
    )

    route = hottest_route[0]
    group = hottest_route[1]

    avg_price = mean(
        item["unit_price"]
        for item in group
    )

    print()
    print(
        "🔥 市場熱度最高路段："
    )

    print(
        f"  {route}"
        f"｜交易 {len(group)} 筆"
        f"｜平均 {avg_price:,.2f} 萬/坪"
    )

    # --------------------------------------------------------
    # 最高價
    # --------------------------------------------------------

    highest_price_route = max(
        valid.items(),
        key=lambda x:
        mean(
            item["unit_price"]
            for item in x[1]
        )
    )

    route = highest_price_route[0]
    group = highest_price_route[1]

    avg_price = mean(
        item["unit_price"]
        for item in group
    )

    print()
    print(
        "💰 平均單價最高路段："
    )

    print(
        f"  {route}"
        f"｜交易 {len(group)} 筆"
        f"｜平均 {avg_price:,.2f} 萬/坪"
    )

    # --------------------------------------------------------
    # 交易量最高
    # --------------------------------------------------------

    highest_volume_route = max(
        valid.items(),
        key=lambda x: len(x[1])
    )

    route = highest_volume_route[0]
    group = highest_volume_route[1]

    avg_price = mean(
        item["unit_price"]
        for item in group
    )

    print()
    print(
        "📊 交易量最高路段："
    )

    print(
        f"  {route}"
        f"｜交易 {len(group)} 筆"
        f"｜平均 {avg_price:,.2f} 萬/坪"
    )


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
        "第七階段："
        "路段行情＋住宅類型＋市場熱點分析"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # 讀取資料
    # --------------------------------------------------------

    records = load_data()

    if not records:

        print()
        print(
            "目前沒有可以分析的資料。"
        )

        return

    # --------------------------------------------------------
    # 分析
    # --------------------------------------------------------

    stats_map = {}

    all_items_map = {}

    for district in sorted(
        TARGET_DISTRICTS
    ):

        items = prepare_district_records(
            records,
            district
        )

        all_items_map[district] = items

        stats = print_district_report(
            district,
            items
        )

        if stats:

            stats_map[district] = stats

            print_market_hotspot_summary(
                items
            )

    # --------------------------------------------------------
    # 士林／北投比較
    # --------------------------------------------------------

    compare_districts(
        stats_map
    )

    # --------------------------------------------------------
    # 完成
    # --------------------------------------------------------

    print()
    print("=" * 70)

    print(
        "第七階段房市分析完成"
    )

    print(
        "路段行情、交易量、價格排名、"
        "市場熱點分析完成"
    )

    print("=" * 70)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
