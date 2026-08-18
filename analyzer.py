# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第五階段＋5.5階段：專業住宅買賣房價分析＋交易資料品質檢查

主要功能：

1. 讀取 data/taipei_transactions.csv
2. 分析士林區、北投區
3. 僅分析「買賣」交易
4. uprice = 交易單價（萬元／坪）
5. tprice = 交易總價（萬元）
6. 若 tprice 無資料，備援使用 price
7. farea = 建物移轉總面積（坪）
8. 排除明顯不合理建物面積
9. IQR 異常交易分析
10. 住宅類型分析
11. 單價區間分析
12. 最高／最低單價案例
13. 士林區／北投區比較

注意：
本程式不會因為「單價很高」就直接刪除交易。
高單價交易先保留，再透過 IQR 判斷是否屬於異常候選。
"""

import csv
import os
from statistics import mean, median


# ============================================================
# 基本設定
# ============================================================

INPUT_FILE = "data/taipei_transactions.csv"

TARGET_DISTRICTS = {
    "士林區",
    "北投區",
}


# ============================================================
# 第 5.5 階段：資料品質設定
# ============================================================

# 太小的建物面積，通常不是正常住宅建物交易
# 例如之前出現的 0.31 坪
MIN_RESIDENTIAL_AREA = 5.0

# 避免非常誇張的大面積資料混入一般住宅行情
MAX_RESIDENTIAL_AREA = 500.0


# ============================================================
# 數字轉換
# ============================================================

def to_float(value):
    """
    將 CSV 欄位轉成 float。

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
        "none",
        "null",
        "NULL",
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
# 四分位數
# ============================================================

def percentile(values, percent):
    """
    計算百分位數。

    percent:
        0.25 = Q1
        0.50 = 中位數
        0.75 = Q3
    """

    if not values:
        return None

    data = sorted(values)

    if len(data) == 1:
        return data[0]

    position = (len(data) - 1) * percent

    lower = int(position)
    upper = lower + 1

    if upper >= len(data):
        return data[lower]

    weight = position - lower

    return (
        data[lower]
        + (data[upper] - data[lower]) * weight
    )


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
        print(f"找不到資料檔案：{INPUT_FILE}")
        print()

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

            # ------------------------------------------------
            # 必要欄位檢查
            # ------------------------------------------------

            required_fields = [
                "case_t",
                "district",
                "uprice",
                "farea",
                "buitype",
                "location",
            ]

            print("必要欄位檢查：")

            for field in required_fields:

                if field in fieldnames:

                    print(f"  ✓ {field}")

                else:

                    print(f"  ✗ {field}（缺少）")

            print()

            if fieldnames:

                print("資料欄位：")
                print(", ".join(fieldnames))

            # ------------------------------------------------
            # 讀取目標行政區
            # ------------------------------------------------

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
# 取得總價
# ============================================================

def get_total_price(row):
    """
    優先使用 tprice。

    若 tprice 沒有資料，
    備援使用 price。

    回傳：
        總價（萬元）
    """

    total_price = to_float(
        row.get("tprice")
    )

    if (
        total_price is not None
        and total_price > 0
    ):

        return total_price

    total_price = to_float(
        row.get("price")
    )

    if (
        total_price is not None
        and total_price > 0
    ):

        return total_price

    return None


# ============================================================
# 第 5.5 階段
# 準備單一行政區住宅交易
# ============================================================

def prepare_district_records(
    records,
    district
):

    valid_items = []

    excluded_count = 0

    excluded_small_area = 0
    excluded_large_area = 0
    excluded_no_price = 0
    excluded_no_area = 0
    excluded_no_unit_price = 0

    for row in records:

        # ----------------------------------------------------
        # 行政區
        # ----------------------------------------------------

        row_district = str(
            row.get("district", "")
        ).strip()

        if row_district != district:

            continue

        # ----------------------------------------------------
        # 只分析買賣
        # ----------------------------------------------------

        case_type = str(
            row.get("case_t", "")
        ).strip()

        if case_type != "買賣":

            continue

        # ----------------------------------------------------
        # 單價
        # ----------------------------------------------------

        unit_price = to_float(
            row.get("uprice")
        )

        if (
            unit_price is None
            or unit_price <= 0
        ):

            excluded_count += 1
            excluded_no_unit_price += 1

            continue

        # ----------------------------------------------------
        # 總價
        # ----------------------------------------------------

        total_price = get_total_price(row)

        if (
            total_price is None
            or total_price <= 0
        ):

            excluded_count += 1
            excluded_no_price += 1

            continue

        # ----------------------------------------------------
        # 建物面積
        # ----------------------------------------------------

        area = to_float(
            row.get("farea")
        )

        if (
            area is None
            or area <= 0
        ):

            excluded_count += 1
            excluded_no_area += 1

            continue

        # ----------------------------------------------------
        # 第 5.5 階段：
        # 排除明顯不合理住宅面積
        # ----------------------------------------------------

        if area < MIN_RESIDENTIAL_AREA:

            excluded_count += 1
            excluded_small_area += 1

            continue

        if area > MAX_RESIDENTIAL_AREA:

            excluded_count += 1
            excluded_large_area += 1

            continue

        # ----------------------------------------------------
        # 建立有效交易資料
        # ----------------------------------------------------

        valid_items.append({

            "row": row,

            "unit_price": unit_price,

            "total_price": total_price,

            "area": area,

        })

    # --------------------------------------------------------
    # 回傳
    # --------------------------------------------------------

    return {
        "items": valid_items,

        "excluded_count": excluded_count,

        "excluded_small_area": excluded_small_area,

        "excluded_large_area": excluded_large_area,

        "excluded_no_price": excluded_no_price,

        "excluded_no_area": excluded_no_area,

        "excluded_no_unit_price": excluded_no_unit_price,
    }


# ============================================================
# 分析住宅類型
# ============================================================

def analyze_building_types(items):

    building_types = {}

    for item in items:

        row = item["row"]

        building_type = str(
            row.get("buitype", "")
        ).strip()

        if building_type == "":

            building_type = "其他"

        building_types[building_type] = (
            building_types.get(
                building_type,
                0
            ) + 1
        )

    if not building_types:

        print("沒有住宅類型資料。")

        return

    sorted_types = sorted(
        building_types.items(),
        key=lambda x: x[1],
        reverse=True
    )

    print()

    print("住宅類型行情：")

    for building_type, count in sorted_types:

        type_items = [

            item

            for item in items

            if str(
                item["row"].get(
                    "buitype",
                    ""
                )
            ).strip() == building_type

        ]

        if not type_items:

            continue

        prices = [
            item["unit_price"]
            for item in type_items
        ]

        print(
            f"  {building_type}"
            f"：{count:,} 筆"
            f"｜平均 "
            f"{mean(prices):,.2f} 萬/坪"
            f"｜中位數 "
            f"{median(prices):,.2f} 萬/坪"
        )


# ============================================================
# 單價區間
# ============================================================

def analyze_price_ranges(items):

    ranges = [

        ("50萬以下", 0, 50),

        ("50~70萬", 50, 70),

        ("70~90萬", 70, 90),

        ("90~120萬", 90, 120),

        ("120萬以上", 120, float("inf")),

    ]

    print()

    print("單價區間分布：")

    for label, lower, upper in ranges:

        count = 0

        for item in items:

            price = item["unit_price"]

            if (
                price >= lower
                and price < upper
            ):

                count += 1

        print(
            f"  {label}：{count:,} 筆"
        )


# ============================================================
# 計算統計
# ============================================================

def calculate_stats(items):

    if not items:

        return None

    unit_prices = [
        item["unit_price"]
        for item in items
    ]

    total_prices = [
        item["total_price"]
        for item in items
        if item["total_price"] > 0
    ]

    areas = [
        item["area"]
        for item in items
        if item["area"] > 0
    ]

    # --------------------------------------------------------
    # Q1 / Q3 / IQR
    # --------------------------------------------------------

    q1 = percentile(
        unit_prices,
        0.25
    )

    q3 = percentile(
        unit_prices,
        0.75
    )

    if (
        q1 is not None
        and q3 is not None
    ):

        iqr = q3 - q1

        iqr_lower = (
            q1 - 1.5 * iqr
        )

        iqr_upper = (
            q3 + 1.5 * iqr
        )

    else:

        iqr = None
        iqr_lower = None
        iqr_upper = None

    # --------------------------------------------------------
    # 主流／異常
    # --------------------------------------------------------

    normal_items = []
    abnormal_items = []

    for item in items:

        price = item["unit_price"]

        if (
            iqr_lower is not None
            and iqr_upper is not None
            and (
                price < iqr_lower
                or price > iqr_upper
            )
        ):

            abnormal_items.append(item)

        else:

            normal_items.append(item)

    normal_prices = [
        item["unit_price"]
        for item in normal_items
    ]

    normal_total = [
        item["total_price"]
        for item in normal_items
    ]

    normal_area = [
        item["area"]
        for item in normal_items
    ]

    if normal_prices:

        normal_average_price = mean(
            normal_prices
        )

        normal_median_price = median(
            normal_prices
        )

        normal_average_total = mean(
            normal_total
        )

        normal_average_area = mean(
            normal_area
        )

    else:

        normal_average_price = None
        normal_median_price = None
        normal_average_total = None
        normal_average_area = None

    return {

        "count": len(items),

        "average_price": mean(
            unit_prices
        ),

        "median_price": median(
            unit_prices
        ),

        "max_price": max(
            unit_prices
        ),

        "min_price": min(
            unit_prices
        ),

        "average_total": mean(
            total_prices
        ) if total_prices else 0,

        "average_area": mean(
            areas
        ) if areas else 0,

        "q1": q1,

        "q3": q3,

        "iqr": iqr,

        "iqr_lower": iqr_lower,

        "iqr_upper": iqr_upper,

        "normal_count": len(
            normal_items
        ),

        "abnormal_count": len(
            abnormal_items
        ),

        "normal_average_price":
            normal_average_price,

        "normal_median_price":
            normal_median_price,

        "normal_average_total":
            normal_average_total,

        "normal_average_area":
            normal_average_area,

        "abnormal_items":
            abnormal_items,

        "normal_items":
            normal_items,

    }


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
            "  沒有偵測到明顯異常價格。"
        )

        return

    # --------------------------------------------------------
    # 高價異常
    # --------------------------------------------------------

    high_abnormal = sorted(
        abnormal,
        key=lambda x: x["unit_price"],
        reverse=True
    )

    print()

    print(
        f"  🔴 高價異常候選："
        f"{len(high_abnormal):,} 筆"
    )

    for item in high_abnormal[:5]:

        row = item["row"]

        print(
            f"    "
            f"{item['unit_price']:,.2f} 萬/坪"
            f"｜"
            f"{row.get('location', '無資料')}"
            f"｜總價 "
            f"{item['total_price']:,.2f} 萬"
            f"｜面積 "
            f"{item['area']:,.2f} 坪"
        )

    # --------------------------------------------------------
    # 低價異常
    # --------------------------------------------------------

    low_abnormal = sorted(
        abnormal,
        key=lambda x: x["unit_price"]
    )

    low_abnormal = [

        item

        for item in low_abnormal

        if (
            stats["iqr_lower"] is not None
            and item["unit_price"]
            < stats["iqr_lower"]
        )

    ]

    print()

    print(
        f"  🔵 低價異常候選："
        f"{len(low_abnormal):,} 筆"
    )

    if not low_abnormal:

        print(
            "    沒有低於 IQR 合理下限的低價異常交易。"
        )

    else:

        for item in low_abnormal[:5]:

            row = item["row"]

            print(
                f"    "
                f"{item['unit_price']:,.2f} 萬/坪"
                f"｜"
                f"{row.get('location', '無資料')}"
                f"｜總價 "
                f"{item['total_price']:,.2f} 萬"
                f"｜面積 "
                f"{item['area']:,.2f} 坪"
            )


# ============================================================
# 單一行政區報告
# ============================================================

def print_district_report(
    district,
    prepared_data
):

    print()

    print("=" * 70)

    print(
        f"{district} 專業房價分析"
    )

    print("=" * 70)

    items = prepared_data["items"]

    if not items:

        print(
            "沒有可分析的住宅買賣資料。"
        )

        return None

    # --------------------------------------------------------
    # 資料品質
    # --------------------------------------------------------

    print()

    print(
        "【資料品質檢查】"
    )

    print(
        f"原始符合行政區／買賣資料："
        f"{len(items) + prepared_data['excluded_count']:,} 筆"
    )

    print(
        f"有效住宅交易："
        f"{len(items):,} 筆"
    )

    print(
        f"品質排除："
        f"{prepared_data['excluded_count']:,} 筆"
    )

    if prepared_data[
        "excluded_small_area"
    ] > 0:

        print(
            f"  └─ 建物面積小於 "
            f"{MIN_RESIDENTIAL_AREA:.1f} 坪："
            f"{prepared_data['excluded_small_area']:,} 筆"
        )

    if prepared_data[
        "excluded_large_area"
    ] > 0:

        print(
            f"  └─ 建物面積大於 "
            f"{MAX_RESIDENTIAL_AREA:.1f} 坪："
            f"{prepared_data['excluded_large_area']:,} 筆"
        )

    if prepared_data[
        "excluded_no_area"
    ] > 0:

        print(
            f"  └─ 無有效建物面積："
            f"{prepared_data['excluded_no_area']:,} 筆"
        )

    if prepared_data[
        "excluded_no_price"
    ] > 0:

        print(
            f"  └─ 無有效總價："
            f"{prepared_data['excluded_no_price']:,} 筆"
        )

    if prepared_data[
        "excluded_no_unit_price"
    ] > 0:

        print(
            f"  └─ 無有效單價："
            f"{prepared_data['excluded_no_unit_price']:,} 筆"
        )

    # --------------------------------------------------------
    # 統計
    # --------------------------------------------------------

    stats = calculate_stats(
        items
    )

    # --------------------------------------------------------
    # 原始行情
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
    # IQR
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

    if (
        stats["normal_average_price"]
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

    # --------------------------------------------------------
    # 住宅類型
    # --------------------------------------------------------

    print()

    print(
        "【三、住宅類型】"
    )

    analyze_building_types(
        items
    )

    # --------------------------------------------------------
    # 價格區間
    # --------------------------------------------------------

    print()

    print(
        "【四、單價區間】"
    )

    analyze_price_ranges(
        items
    )

    # --------------------------------------------------------
    # 異常交易
    # --------------------------------------------------------

    print()

    print(
        "【五、異常交易候選】"
    )

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
    # 最低單價
    # --------------------------------------------------------

    lowest = min(
        items,
        key=lambda x: x["unit_price"]
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

    # --------------------------------------------------------
    # 價差
    # --------------------------------------------------------

    shilin_main = (
        shilin["normal_average_price"]
    )

    beitou_main = (
        beitou["normal_average_price"]
    )

    if (
        shilin_main is None
        or beitou_main is None
    ):

        print()

        print(
            "主流平均單價資料不足，"
            "無法計算價格差異。"
        )

        return

    price_difference = (
        shilin_main
        - beitou_main
    )

    if beitou_main != 0:

        percentage = (
            price_difference
            / beitou_main
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
        "第五階段＋5.5階段："
        "專業住宅買賣房價分析"
        "＋交易資料品質檢查"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # 讀取資料
    # --------------------------------------------------------

    records = load_data()

    print()

    if not records:

        print(
            "目前沒有可以分析的資料。"
        )

        return

    # --------------------------------------------------------
    # 分析兩區
    # --------------------------------------------------------

    stats_map = {}

    for district in sorted(
        TARGET_DISTRICTS
    ):

        prepared_data = (
            prepare_district_records(
                records,
                district
            )
        )

        stats = print_district_report(
            district,
            prepared_data
        )

        if stats:

            stats_map[district] = stats

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
        "第五階段＋5.5階段房市分析完成"
    )

    print("=" * 70)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
