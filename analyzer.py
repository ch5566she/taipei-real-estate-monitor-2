# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第六階段：路段＋住宅類型行情分析

功能：
1. 讀取台北市交易資料
2. 篩選士林區／北投區
3. 只分析「買賣」
4. 住宅資料品質檢查
5. 排除建物面積小於 5 坪資料
6. IQR 異常價格分析
7. 行政區整體行情
8. 住宅類型行情
9. 單價區間
10. 路段行情
11. 路段＋住宅類型交叉分析
12. 士林區／北投區比較

主要資料欄位：

case_t   = 交易類型
district = 行政區
uprice   = 交易單價（萬元／坪）
tprice   = 交易總價（萬元）
farea    = 建物移轉總面積（坪）
buitype  = 建築型態
location = 地址
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

# 路段／住宅類型分析最低樣本數
# 避免只有 1 筆交易就被誤認為市場行情
MIN_GROUP_COUNT = 2

# 一般住宅最低建物面積
MIN_RESIDENTIAL_AREA = 5.0


# ============================================================
# 數字轉換
# ============================================================

def to_float(value):
    """
    將 CSV 欄位轉成數字。
    無法轉換時回傳 None。
    """

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
# 地址清理
# ============================================================

def clean_location(location):

    if location is None:
        return ""

    text = str(location).strip()

    if not text:
        return ""

    text = text.replace("\u3000", "")

    text = re.sub(
        r"\s+",
        "",
        text
    )

    return text


# ============================================================
# 路段擷取
# ============================================================

def extract_road(location):
    """
    從地址中擷取主要道路名稱。

    例如：

    德行東路109巷3號一樓
    → 德行東路

    中央北路二段320巷7號
    → 中央北路二段

    石牌路三段
    → 石牌路三段

    無法辨識時：
    → 未辨識路段
    """

    text = clean_location(location)

    if not text:
        return "未辨識路段"

    # --------------------------------------------------------
    # 先抓「路／街／大道＋段」
    # --------------------------------------------------------

    pattern_with_section = (
        r"("
        r"[\u4e00-\u9fff]{1,15}"
        r"(?:路|街|大道)"
        r"(?:[一二三四五六七八九十\d]+段)"
        r")"
    )

    match = re.search(
        pattern_with_section,
        text
    )

    if match:
        return match.group(1)

    # --------------------------------------------------------
    # 再抓沒有「段」的路／街／大道
    # --------------------------------------------------------

    pattern_road = (
        r"("
        r"[\u4e00-\u9fff]{1,15}"
        r"(?:路|街|大道)"
        r")"
    )

    match = re.search(
        pattern_road,
        text
    )

    if match:
        return match.group(1)

    # --------------------------------------------------------
    # 最後抓巷
    # --------------------------------------------------------

    pattern_lane = (
        r"("
        r"[\u4e00-\u9fff]{1,15}"
        r"巷"
        r")"
    )

    match = re.search(
        pattern_lane,
        text
    )

    if match:
        return match.group(1)

    return "未辨識路段"


# ============================================================
# 住宅類型標準化
# ============================================================

def normalize_building_type(value):

    if value is None:
        return "其他"

    text = str(value).strip()

    if text == "":
        return "其他"

    return text


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

        # ----------------------------------------------------
        # 必要欄位
        # ----------------------------------------------------

        required_fields = [
            "case_t",
            "district",
            "uprice",
            "price",
            "farea",
            "buitype",
            "location",
        ]

        print()
        print("必要欄位檢查：")

        missing_fields = []

        for field in required_fields:

            if field in fieldnames:

                print(
                    f"  ✓ {field}"
                )

            else:

                print(
                    f"  ✗ {field}"
                )

                missing_fields.append(field)

        if missing_fields:

            print()
            print(
                "錯誤：CSV 缺少必要欄位："
            )

            print(
                ", ".join(missing_fields)
            )

            return []

        print()
        print("資料欄位：")
        print(
            ", ".join(fieldnames)
        )

        # ----------------------------------------------------
        # 篩選行政區
        # ----------------------------------------------------

        for row in reader:

            district = str(
                row.get(
                    "district",
                    ""
                )
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
# 準備行政區住宅資料
# ============================================================

def prepare_district_records(
    records,
    district
):

    items = []

    raw_count = 0

    invalid_unit_price = 0
    invalid_total_price = 0
    invalid_area = 0
    tiny_area = 0

    for row in records:

        row_district = str(
            row.get(
                "district",
                ""
            )
        ).strip()

        if row_district != district:
            continue

        # ----------------------------------------------------
        # 只分析買賣
        # ----------------------------------------------------

        case_type = str(
            row.get(
                "case_t",
                ""
            )
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

            invalid_unit_price += 1
            continue

        # ----------------------------------------------------
        # 總價
        # ----------------------------------------------------

        total_price = to_float(
            row.get("tprice")
        )

        if total_price is None or total_price <= 0:

            invalid_total_price += 1
            continue

        # ----------------------------------------------------
        # 建物面積
        # ----------------------------------------------------

        area = to_float(
            row.get("farea")
        )

        if area is None or area <= 0:

            invalid_area += 1
            continue

        # ----------------------------------------------------
        # 排除極小面積
        # ----------------------------------------------------

        if area < MIN_RESIDENTIAL_AREA:

            tiny_area += 1
            continue

        # ----------------------------------------------------
        # 地址
        # ----------------------------------------------------

        location = clean_location(
            row.get(
                "location",
                ""
            )
        )

        # ----------------------------------------------------
        # 路段
        # ----------------------------------------------------

        road = extract_road(
            location
        )

        # ----------------------------------------------------
        # 住宅類型
        # ----------------------------------------------------

        building_type = normalize_building_type(
            row.get(
                "buitype",
                ""
            )
        )

        items.append({

            "row": row,

            "unit_price": unit_price,

            "total_price": total_price,

            "area": area,

            "road": road,

            "building_type": building_type,

        })

    # ========================================================
    # 資料品質報告
    # ========================================================

    print()
    print(
        f"{district}【資料品質檢查】"
    )

    print(
        f"原始符合行政區／買賣資料："
        f"{raw_count:,} 筆"
    )

    print(
        f"有效住宅交易："
        f"{len(items):,} 筆"
    )

    excluded = (
        invalid_unit_price
        + invalid_total_price
        + invalid_area
        + tiny_area
    )

    print(
        f"品質排除："
        f"{excluded:,} 筆"
    )

    if invalid_area:

        print(
            f"  └─ 無有效建物面積："
            f"{invalid_area:,} 筆"
        )

    if invalid_unit_price:

        print(
            f"  └─ 無有效單價："
            f"{invalid_unit_price:,} 筆"
        )

    if invalid_total_price:

        print(
            f"  └─ 無有效總價："
            f"{invalid_total_price:,} 筆"
        )

    if tiny_area:

        print(
            f"  └─ 建物面積低於 "
            f"{MIN_RESIDENTIAL_AREA:.1f} 坪："
            f"{tiny_area:,} 筆"
        )

    return items


# ============================================================
# 百分位數
# ============================================================

def percentile(
    values,
    p
):

    if not values:
        return None

    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return sorted_values[0]

    index = (
        (len(sorted_values) - 1)
        * p
        / 100
    )

    lower = int(index)

    upper = lower + 1

    if upper >= len(sorted_values):

        return sorted_values[-1]

    fraction = index - lower

    return (
        sorted_values[lower]
        + (
            sorted_values[upper]
            - sorted_values[lower]
        )
        * fraction
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

    # --------------------------------------------------------
    # Q1 / Q3
    # --------------------------------------------------------

    q1 = percentile(
        unit_prices,
        25
    )

    q3 = percentile(
        unit_prices,
        75
    )

    iqr = q3 - q1

    iqr_lower = (
        q1
        - 1.5 * iqr
    )

    iqr_upper = (
        q3
        + 1.5 * iqr
    )

    # --------------------------------------------------------
    # 主流交易
    # --------------------------------------------------------

    normal_items = [
        item
        for item in items
        if (
            iqr_lower
            <= item["unit_price"]
            <= iqr_upper
        )
    ]

    # --------------------------------------------------------
    # 異常交易
    # --------------------------------------------------------

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

        "count":
            len(items),

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

        "q1":
            q1,

        "q3":
            q3,

        "iqr_lower":
            iqr_lower,

        "iqr_upper":
            iqr_upper,

        "normal_count":
            len(normal_items),

        "abnormal_count":
            len(abnormal_items),

        "abnormal_items":
            abnormal_items,

        "normal_average_price":
            (
                mean(normal_prices)
                if normal_prices
                else None
            ),

        "normal_median_price":
            (
                median(normal_prices)
                if normal_prices
                else None
            ),

        "normal_average_total":
            (
                mean(normal_totals)
                if normal_totals
                else None
            ),

        "normal_average_area":
            (
                mean(normal_areas)
                if normal_areas
                else None
            ),
    }


# ============================================================
# 住宅類型分析
# ============================================================

def analyze_building_types(items):

    groups = {}

    for item in items:

        building_type = (
            item["building_type"]
        )

        if building_type not in groups:

            groups[building_type] = []

        groups[
            building_type
        ].append(item)

    print()
    print("住宅類型行情：")

    sorted_groups = sorted(
        groups.items(),
        key=lambda x: (
            -len(x[1]),
            x[0]
        )
    )

    for (
        building_type,
        group
    ) in sorted_groups:

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
# 單價區間
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

            ranges[
                "50萬以下"
            ] += 1

        elif price < 70:

            ranges[
                "50～70萬"
            ] += 1

        elif price < 90:

            ranges[
                "70～90萬"
            ] += 1

        elif price < 120:

            ranges[
                "90～120萬"
            ] += 1

        else:

            ranges[
                "120萬以上"
            ] += 1

    for label, count in ranges.items():

        print(
            f"  {label}："
            f"{count:,} 筆"
        )


# ============================================================
# IQR 異常交易
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
            "  沒有偵測到明顯異常價格。"
        )

        return

    # --------------------------------------------------------
    # 高價異常
    # --------------------------------------------------------

    high_abnormal = [
        item
        for item in abnormal
        if (
            item["unit_price"]
            > stats["iqr_upper"]
        )
    ]

    print()
    print(
        f"  🔴 高價異常候選："
        f"{len(high_abnormal):,} 筆"
    )

    high_abnormal = sorted(
        high_abnormal,
        key=lambda x:
            x["unit_price"],
        reverse=True
    )[:5]

    for item in high_abnormal:

        row = item["row"]

        print(
            f"    "
            f"{item['unit_price']:,.2f} 萬/坪"
            f"｜{row.get('location', '無資料')}"
            f"｜總價 "
            f"{item['total_price']:,.2f} 萬"
            f"｜面積 "
            f"{item['area']:,.2f} 坪"
        )

    # --------------------------------------------------------
    # 低價異常
    # --------------------------------------------------------

    low_abnormal = [
        item
        for item in abnormal
        if (
            item["unit_price"]
            < stats["iqr_lower"]
        )
    ]

    print()
    print(
        f"  🔵 低價異常候選："
        f"{len(low_abnormal):,} 筆"
    )

    low_abnormal = sorted(
        low_abnormal,
        key=lambda x:
            x["unit_price"]
    )[:5]

    if not low_abnormal:

        print(
            "    沒有低於 IQR 合理下限的低價異常交易。"
        )

    for item in low_abnormal:

        row = item["row"]

        print(
            f"    "
            f"{item['unit_price']:,.2f} 萬/坪"
            f"｜{row.get('location', '無資料')}"
            f"｜總價 "
            f"{item['total_price']:,.2f} 萬"
            f"｜面積 "
            f"{item['area']:,.2f} 坪"
        )


# ============================================================
# 路段行情分析
# ============================================================

def analyze_roads(items):

    groups = {}

    for item in items:

        road = item["road"]

        if road not in groups:

            groups[road] = []

        groups[
            road
        ].append(item)

    print()
    print("【六、路段行情分析】")

    print(
        "僅顯示至少 "
        f"{MIN_GROUP_COUNT} 筆交易的路段："
    )

    valid_groups = []

    for road, group in groups.items():

        if (
            len(group)
            >= MIN_GROUP_COUNT
        ):

            valid_groups.append(
                (
                    road,
                    group
                )
            )

    # --------------------------------------------------------
    # 依平均單價排序
    # --------------------------------------------------------

    valid_groups.sort(
        key=lambda x: (
            -mean(
                item["unit_price"]
                for item in x[1]
            ),
            -len(x[1]),
            x[0]
        )
    )

    if not valid_groups:

        print(
            "  沒有足夠樣本的路段。"
        )

        return

    for road, group in valid_groups:

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {road}"
            f"｜{len(group):,} 筆"
            f"｜平均 "
            f"{mean(prices):,.2f} 萬/坪"
            f"｜中位數 "
            f"{median(prices):,.2f} 萬/坪"
        )


# ============================================================
# 路段＋住宅類型
# ============================================================

def analyze_road_building_type(items):

    groups = {}

    for item in items:

        key = (
            item["road"],
            item["building_type"]
        )

        if key not in groups:

            groups[key] = []

        groups[key].append(item)

    print()
    print(
        "【七、路段＋住宅類型交叉分析】"
    )

    print(
        "僅顯示至少 "
        f"{MIN_GROUP_COUNT} 筆交易的組別："
    )

    valid_groups = []

    for key, group in groups.items():

        if (
            len(group)
            >= MIN_GROUP_COUNT
        ):

            valid_groups.append(
                (
                    key,
                    group
                )
            )

    valid_groups.sort(
        key=lambda x: (
            -mean(
                item["unit_price"]
                for item in x[1]
            ),
            -len(x[1]),
            x[0][0],
            x[0][1]
        )
    )

    if not valid_groups:

        print(
            "  沒有足夠樣本的交叉組別。"
        )

        return

    for (
        key,
        group
    ) in valid_groups:

        road = key[0]

        building_type = key[1]

        prices = [
            item["unit_price"]
            for item in group
        ]

        print(
            f"  {road}"
            f"｜{building_type}"
            f"｜{len(group):,} 筆"
            f"｜平均 "
            f"{mean(prices):,.2f} 萬/坪"
            f"｜中位數 "
            f"{median(prices):,.2f} 萬/坪"
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
        f"{district} 第六階段專業房價分析"
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

    # ========================================================
    # 一、原始交易行情
    # ========================================================

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

    # ========================================================
    # 二、IQR
    # ========================================================

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

    if (
        stats[
            "normal_average_price"
        ]
        is not None
    ):

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

    # ========================================================
    # 三、住宅類型
    # ========================================================

    print()
    print("【三、住宅類型】")

    analyze_building_types(
        items
    )

    # ========================================================
    # 四、單價區間
    # ========================================================

    print()
    print("【四、單價區間】")

    analyze_price_ranges(
        items
    )

    # ========================================================
    # 五、異常交易
    # ========================================================

    print()
    print("【五、異常交易候選】")

    show_abnormal_cases(
        stats
    )

    # ========================================================
    # 最高單價
    # ========================================================

    highest = max(
        items,
        key=lambda x:
            x["unit_price"]
    )

    highest_row = (
        highest["row"]
    )

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

    # ========================================================
    # 最低單價
    # ========================================================

    lowest = min(
        items,
        key=lambda x:
            x["unit_price"]
    )

    lowest_row = (
        lowest["row"]
    )

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

    # ========================================================
    # 六、路段行情
    # ========================================================

    analyze_roads(
        items
    )

    # ========================================================
    # 七、路段＋住宅類型
    # ========================================================

    analyze_road_building_type(
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

    # ========================================================
    # 價格差異
    # ========================================================

    price_difference = (
        shilin[
            "normal_average_price"
        ]
        -
        beitou[
            "normal_average_price"
        ]
    )

    if (
        beitou[
            "normal_average_price"
        ]
        != 0
    ):

        percentage = (
            price_difference
            /
            beitou[
                "normal_average_price"
            ]
            * 100
        )

    else:

        percentage = 0

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
            f"{abs(price_difference):,.2f} 萬/坪"
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
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "台北市士林區／北投區房市監控系統"
    )

    print(
        "第六階段：路段＋住宅類型行情分析"
    )

    print("=" * 70)

    # ========================================================
    # 讀取資料
    # ========================================================

    records = load_data()

    if not records:

        print()
        print(
            "目前沒有可以分析的資料。"
        )

        return

    # ========================================================
    # 分析兩區
    # ========================================================

    stats_map = {}

    for district in sorted(
        TARGET_DISTRICTS
    ):

        items = (
            prepare_district_records(
                records,
                district
            )
        )

        stats = (
            print_district_report(
                district,
                items
            )
        )

        if stats:

            stats_map[
                district
            ] = stats

    # ========================================================
    # 士林／北投比較
    # ========================================================

    compare_districts(
        stats_map
    )

    # ========================================================
    # 完成
    # ========================================================

    print()
    print("=" * 70)

    print(
        "第六階段房市分析完成"
    )

    print("=" * 70)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
