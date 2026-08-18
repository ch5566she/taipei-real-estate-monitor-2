# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第五階段：專業住宅買賣房價分析

功能：
1. 讀取台北市交易資料
2. 分析士林區、北投區
3. 只分析「買賣」
4. 使用 uprice 作為交易單價
5. 使用 tprice 作為交易總價
6. 使用 farea 作為建物面積
7. IQR 異常值偵測
8. 原始行情與主流行情分開統計
9. 住宅類型統計
10. 士林區／北投區比較
11. 高低價異常案例
12. 價格區間分布
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
# 四分位數
# ============================================================

def percentile(values, p):

    """
    計算簡易線性插值百分位數。
    p 範圍：0～1
    """

    if not values:
        return None

    data = sorted(values)

    if len(data) == 1:
        return data[0]

    position = (len(data) - 1) * p

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
# IQR 異常值
# ============================================================

def get_iqr_bounds(values):

    """
    使用 IQR 方法判斷異常價格。

    下限 = Q1 - 1.5 × IQR
    上限 = Q3 + 1.5 × IQR
    """

    if len(values) < 4:

        return None, None

    q1 = percentile(values, 0.25)

    q3 = percentile(values, 0.75)

    iqr = q3 - q1

    lower = q1 - 1.5 * iqr

    upper = q3 + 1.5 * iqr

    return lower, upper


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
        # 檢查必要欄位
        # ----------------------------------------------------

        required_fields = [
            "case_t",
            "district",
            "uprice",
            "tprice",
            "farea",
            "buitype",
            "location",
        ]

        print()
        print("必要欄位檢查：")

        for field in required_fields:

            if field in fieldnames:

                print(
                    f"  ✓ {field}"
                )

            else:

                print(
                    f"  ✗ 缺少 {field}"
                )

        # ----------------------------------------------------
        # 讀取指定行政區
        # ----------------------------------------------------

        for row in reader:

            district = str(
                row.get("district", "")
            ).strip()

            if district not in TARGET_DISTRICTS:

                continue

            records.append(row)

    return records


# ============================================================
# 整理單一行政區有效交易
# ============================================================

def prepare_district_records(records, district):

    result = []

    for row in records:

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

        if unit_price is None or unit_price <= 0:
            continue

        # ----------------------------------------------------
        # 總價
        # ----------------------------------------------------

        total_price = to_float(
            row.get("tprice")
        )

        if total_price is None or total_price <= 0:
            continue

        # ----------------------------------------------------
        # 建物面積
        # ----------------------------------------------------

        area = to_float(
            row.get("farea")
        )

        # ----------------------------------------------------
        # 如果面積缺失
        # 用總價／單價估算
        # ----------------------------------------------------

        if area is None or area <= 0:

            area = total_price / unit_price

        if area <= 0:
            continue

        result.append({

            "row": row,

            "unit_price": unit_price,

            "total_price": total_price,

            "area": area,

        })

    return result


# ============================================================
# 行情統計
# ============================================================

def calculate_stats(items):

    if not items:
        return None

    prices = [
        x["unit_price"]
        for x in items
    ]

    totals = [
        x["total_price"]
        for x in items
    ]

    areas = [
        x["area"]
        for x in items
    ]

    lower, upper = get_iqr_bounds(prices)

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
        x["unit_price"]
        for x in normal_items
    ]

    normal_totals = [
        x["total_price"]
        for x in normal_items
    ]

    normal_areas = [
        x["area"]
        for x in normal_items
    ]

    return {

        "count": len(items),

        "prices": prices,

        "totals": totals,

        "areas": areas,

        "average_price": mean(prices),

        "median_price": median(prices),

        "max_price": max(prices),

        "min_price": min(prices),

        "average_total": mean(totals),

        "average_area": mean(areas),

        "q1": percentile(prices, 0.25),

        "q3": percentile(prices, 0.75),

        "iqr_lower": lower,

        "iqr_upper": upper,

        "normal_items": normal_items,

        "abnormal_items": abnormal_items,

        "normal_count": len(normal_items),

        "abnormal_count": len(abnormal_items),

        "normal_average_price": (
            mean(normal_prices)
            if normal_prices
            else None
        ),

        "normal_median_price": (
            median(normal_prices)
            if normal_prices
            else None
        ),

        "normal_average_total": (
            mean(normal_totals)
            if normal_totals
            else None
        ),

        "normal_average_area": (
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

        row = item["row"]

        building_type = str(
            row.get("buitype", "")
        ).strip()

        if building_type == "":
            building_type = "其他"

        if building_type not in groups:

            groups[building_type] = []

        groups[building_type].append(item)

    print()
    print("住宅類型行情：")

    sorted_groups = sorted(
        groups.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    for building_type, group in sorted_groups:

        prices = [
            x["unit_price"]
            for x in group
        ]

        print(
            f"  {building_type}"
            f"：{len(group):,} 筆"
            f"｜平均 {mean(prices):,.2f} 萬/坪"
            f"｜中位數 {median(prices):,.2f} 萬/坪"
        )


# ============================================================
# 價格區間分析
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

    for name, count in ranges.items():

        print(
            f"  {name}：{count:,} 筆"
        )


# ============================================================
# 顯示異常案例
# ============================================================

def show_abnormal_cases(stats):

    abnormal = stats.get("abnormal_items", [])

    print()
    print(
        f"⚠️ IQR 異常交易候選："
        f"{len(abnormal):,} 筆"
    )

    if not abnormal:

        print("  沒有偵測到明顯異常價格。")

        return

    # --------------------------------------------------------
    # 取得 IQR 合理上下限
    # --------------------------------------------------------

    lower_limit = stats.get("iqr_lower")
    upper_limit = stats.get("iqr_upper")

    # --------------------------------------------------------
    # 分開高價異常與低價異常
    #
    # 高價異常：
    # 單價 > IQR 合理上限
    #
    # 低價異常：
    # 單價 < IQR 合理下限
    # --------------------------------------------------------

    if upper_limit is not None:

        high_abnormal = [
            item
            for item in abnormal
            if item["unit_price"] > upper_limit
        ]

    else:

        high_abnormal = []


    if lower_limit is not None:

        low_abnormal = [
            item
            for item in abnormal
            if item["unit_price"] < lower_limit
        ]

    else:

        low_abnormal = []

    # --------------------------------------------------------
    # 高價異常
    # --------------------------------------------------------

    print()
    print(
        f"  🔴 高價異常候選："
        f"{len(high_abnormal):,} 筆"
    )

    if high_abnormal:

        high_abnormal = sorted(
            high_abnormal,
            key=lambda x: x["unit_price"],
            reverse=True
        )[:5]

        for item in high_abnormal:

            row = item["row"]

            print(
                f"    {item['unit_price']:,.2f} 萬/坪"
                f"｜{row.get('location', '無資料')}"
                f"｜總價 {item['total_price']:,.2f} 萬"
                f"｜面積 {item['area']:,.2f} 坪"
            )

    else:

        print(
            "    沒有低於 IQR 合理上限以上的高價異常交易。"
        )

    # --------------------------------------------------------
    # 低價異常
    # --------------------------------------------------------

    print()
    print(
        f"  🔵 低價異常候選："
        f"{len(low_abnormal):,} 筆"
    )

    if low_abnormal:

        low_abnormal = sorted(
            low_abnormal,
            key=lambda x: x["unit_price"]
        )[:5]

        for item in low_abnormal:

            row = item["row"]

            print(
                f"    {item['unit_price']:,.2f} 萬/坪"
                f"｜{row.get('location', '無資料')}"
                f"｜總價 {item['total_price']:,.2f} 萬"
                f"｜面積 {item['area']:,.2f} 坪"
            )

    else:

        print(
            "    沒有低於 IQR 合理下限的低價異常交易。"
        )


# ============================================================
# 單一行政區報告
# ============================================================

def print_district_report(
    district,
    items
):

    print()
    print("=" * 70)
    print(f"{district} 專業房價分析")
    print("=" * 70)

    if not items:

        print(
            "沒有可分析的住宅買賣資料。"
        )

        return None

    stats = calculate_stats(items)

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

    print()
    print("=" * 70)

    return stats


# ============================================================
# 士林／北投比較
# ============================================================

def compare_districts(stats_map):

    shilin = stats_map.get("士林區")

    beitou = stats_map.get("北投區")

    if not shilin or not beitou:

        print()
        print(
            "無法進行士林區／北投區比較。"
        )

        return

    print()
    print("=" * 70)
    print("士林區 vs 北投區 房價比較")
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

    price_difference = (
        shilin["normal_average_price"]
        - beitou["normal_average_price"]
    )

    if beitou["normal_average_price"] != 0:

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
    print("台北市士林區／北投區房市監控系統")
    print("第五階段：專業住宅買賣房價分析")
    print("=" * 70)

    # --------------------------------------------------------
    # 讀取資料
    # --------------------------------------------------------

    records = load_data()

    print()

    print(
        f"讀取到士林區／北投區資料："
        f"{len(records):,} 筆"
    )

    if not records:

        print(
            "目前沒有可以分析的資料。"
        )

        return

    # --------------------------------------------------------
    # 分析兩區
    # --------------------------------------------------------

    stats_map = {}

    for district in sorted(TARGET_DISTRICTS):

        items = prepare_district_records(
            records,
            district
        )

        stats = print_district_report(
            district,
            items
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
    print("第五階段房市分析完成")
    print("=" * 70)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":

    main()
