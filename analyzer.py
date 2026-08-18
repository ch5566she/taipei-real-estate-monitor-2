# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第四階段：住宅買賣房價分析

正確資料欄位：
uprice = 交易單價（萬元／坪）
tprice = 交易總價（萬元）
farea  = 建物移轉總面積（坪）
pu_area = 共有部分面積（不作為交易單價）
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
    """
    將 CSV 欄位轉成數字。
    無法轉換時回傳 None。
    """

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    # 常見無效值
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

    # 移除千分位逗號
    value = value.replace(",", "")

    try:
        return float(value)

    except (ValueError, TypeError):
        return None


# ============================================================
# 讀取資料
# ============================================================

def load_data():

    print()
    print("=" * 60)
    print("讀取房價資料")
    print("=" * 60)

    if not os.path.exists(INPUT_FILE):

        print(f"找不到資料檔案：{INPUT_FILE}")

        return []

    records = []

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as csvfile:

        reader = csv.DictReader(csvfile)

        print(f"資料欄位數：{len(reader.fieldnames or [])}")

        if reader.fieldnames:
            print("資料欄位：")
            print(", ".join(reader.fieldnames))

        for row in reader:

            district = str(
                row.get("district", "")
            ).strip()

            if district not in TARGET_DISTRICTS:
                continue

            records.append(row)

    return records


# ============================================================
# 分析單一行政區
# ============================================================

def analyze_district(records, district):
    """分析指定行政區的住宅買賣房價"""

    district_records = []

    # ========================================================
    # 篩選指定行政區
    # ========================================================

    for row in records:

        row_district = str(
            row.get("district", "")
        ).strip()

        if row_district != district:
            continue

        # ====================================================
        # 只分析「買賣」
        # ====================================================

        case_type = str(
            row.get("case_t", "")
        ).strip()

        if case_type != "買賣":
            continue

        # ====================================================
        # 單價
        # uprice = 單價（萬元/坪）
        # ====================================================

        unit_price = to_float(
            row.get("uprice")
        )

        # 沒有單價或單價 <= 0
        if unit_price is None or unit_price <= 0:
            continue

        # ====================================================
        # 總價
        # price = 總價（萬元）
        # ====================================================

        total_price = to_float(
            row.get("price")
        )

        # 沒有總價或總價 <= 0
        if total_price is None or total_price <= 0:
            continue

        # ====================================================
        # 建物面積
        # farea = 建物面積（坪）
        # ====================================================

        area = to_float(
            row.get("farea")
        )

        # ====================================================
        # 重要：
        # 沒有建物面積的交易排除
        #
        # 這可以排除：
        # 土地交易
        # 地號交易
        # 非住宅建物交易
        # ====================================================

        if area is None or area <= 0:
            continue

        # ====================================================
        # 保存有效住宅交易
        # ====================================================

        district_records.append({
            "row": row,
            "unit_price": unit_price,
            "total_price": total_price,
            "area": area
        })

    # ========================================================
    # 沒有資料
    # ========================================================

    if not district_records:

        print()
        print("=" * 60)
        print(f"{district} 房價分析")
        print("=" * 60)
        print("沒有可分析的住宅買賣資料。")

        return

    # ========================================================
    # 基本統計
    # ========================================================

    unit_prices = [
        item["unit_price"]
        for item in district_records
    ]

    total_prices = [
        item["total_price"]
        for item in district_records
        if item["total_price"] is not None
        and item["total_price"] > 0
    ]

    areas = [
        item["area"]
        for item in district_records
        if item["area"] is not None
        and item["area"] > 0
    ]

    # ========================================================
    # 房價分析標題
    # ========================================================

    print()
    print("=" * 60)
    print(f"{district} 房價分析")
    print("=" * 60)

    # ========================================================
    # 有效交易筆數
    # ========================================================

    print(
        f"有效住宅買賣筆數：{len(district_records):,} 筆"
    )

    # ========================================================
    # 平均單價
    # ========================================================

    print(
        f"平均單價：{mean(unit_prices):.2f} 萬元/坪"
    )

    # ========================================================
    # 中位數單價
    # ========================================================

    print(
        f"中位數單價：{median(unit_prices):.2f} 萬元/坪"
    )

    # ========================================================
    # 最高單價
    # ========================================================

    print(
        f"最高單價：{max(unit_prices):.2f} 萬元/坪"
    )

    # ========================================================
    # 最低單價
    # ========================================================

    print(
        f"最低單價：{min(unit_prices):.2f} 萬元/坪"
    )

    # ========================================================
    # 平均總價
    # ========================================================

    if total_prices:

        print(
            f"平均總價：{mean(total_prices):,.2f} 萬元"
        )

    else:

        print(
            "平均總價：沒有有效資料"
        )

    # ========================================================
    # 平均建物面積
    # ========================================================

    if areas:

        print(
            f"平均建物面積：{mean(areas):.2f} 坪"
        )

    else:

        print(
            "平均建物面積：沒有有效資料"
        )

    # ========================================================
    # 住宅類型統計
    # ========================================================

    building_types = {}

    for item in district_records:

        row = item["row"]

        building_type = str(
            row.get("buitype", "")
        ).strip()

        if building_type == "":
            building_type = "其他"

        building_types[building_type] = (
            building_types.get(building_type, 0) + 1
        )

    print()
    print("住宅類型統計：")

    sorted_types = sorted(
        building_types.items(),
        key=lambda x: x[1],
        reverse=True
    )

    for building_type, count in sorted_types:

        print(
            f"  {building_type}：{count} 筆"
        )

    # ========================================================
    # 最高單價案例
    # ========================================================

    highest = max(
        district_records,
        key=lambda x: x["unit_price"]
    )

    highest_row = highest["row"]

    print()
    print("最高單價案例：")

    print(
        f"  單價：{highest['unit_price']:.2f} 萬元/坪"
    )

    print(
        f"  地址：{highest_row.get('location', '無資料')}"
    )

    print(
        f"  總價：{highest['total_price']:,.2f} 萬元"
    )

    print(
        f"  面積：{highest['area']:.2f} 坪"
    )

    # ========================================================
    # 最低單價案例
    # ========================================================

    lowest = min(
        district_records,
        key=lambda x: x["unit_price"]
    )

    lowest_row = lowest["row"]

    print()
    print("最低單價案例：")

    print(
        f"  單價：{lowest['unit_price']:.2f} 萬元/坪"
    )

    print(
        f"  地址：{lowest_row.get('location', '無資料')}"
    )

    print(
        f"  總價：{lowest['total_price']:,.2f} 萬元"
    )

    print(
        f"  面積：{lowest['area']:.2f} 坪"
    )
    print("=" * 60)


# ============================================================
# 程式入口
# ============================================================

# ========================================================
# 主程式
# ========================================================

def main():

    print("=" * 60)
    print("台北市士林區／北投區房市監控系統")
    print("第四階段：住宅買賣房價分析")
    print("=" * 60)

    # ====================================================
    # 讀取資料
    # ====================================================

    records = load_data()

    print(
        f"\n讀取到士林區／北投區資料：{len(records):,} 筆"
    )

    # ====================================================
    # 沒有資料
    # ====================================================

    if not records:

        print("目前沒有可以分析的資料。")
        return

    # ====================================================
    # 分析兩個行政區
    # ====================================================

    for district in sorted(TARGET_DISTRICTS):

        analyze_district(
            records,
            district
        )

    # ====================================================
    # 完成
    # ====================================================

    print()
    print("=" * 60)
    print("房市分析完成")
    print("=" * 60)


# ========================================================
# 程式入口
# ========================================================

if __name__ == "__main__":
    main()
