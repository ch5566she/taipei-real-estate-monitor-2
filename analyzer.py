# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第四階段：住宅買賣房價分析

CSV 實際資料欄位：

case_t   = 交易類型
district = 行政區
uprice   = 交易單價（萬元／坪）
tprice   = 交易總價（萬元）
farea    = 建物移轉總面積（坪）
buitype  = 建物型態
location = 地址

注意：
不要使用 price 作為交易總價。
本資料正確欄位是 tprice。
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

        fieldnames = reader.fieldnames or []

        print(
            f"資料欄位數：{len(fieldnames)}"
        )

        print("資料欄位：")

        print(
            ", ".join(fieldnames)
        )

        # ----------------------------------------------------
        # 檢查重要欄位
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
        print("重要欄位檢查：")

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
# 分析單一行政區
# ============================================================

def analyze_district(records, district):

    """
    分析指定行政區的住宅買賣房價。
    """

    # --------------------------------------------------------
    # 統計各階段資料
    # --------------------------------------------------------

    district_count = 0
    sale_count = 0
    unit_price_count = 0
    total_price_count = 0
    area_count = 0

    district_records = []

    # --------------------------------------------------------
    # 篩選指定行政區
    # --------------------------------------------------------

    for row in records:

        row_district = str(
            row.get("district", "")
        ).strip()

        if row_district != district:

            continue

        district_count += 1

        # ----------------------------------------------------
        # 只分析「買賣」
        # ----------------------------------------------------

        case_type = str(
            row.get("case_t", "")
        ).strip()

        if case_type != "買賣":

            continue

        sale_count += 1

        # ----------------------------------------------------
        # 單價
        #
        # uprice = 萬元／坪
        # ----------------------------------------------------

        unit_price = to_float(
            row.get("uprice")
        )

        if unit_price is None or unit_price <= 0:

            continue

        unit_price_count += 1

        # ----------------------------------------------------
        # 總價
        #
        # ★★★ 重要 ★★★
        #
        # 正確欄位是 tprice
        # 不是 price
        # ----------------------------------------------------

        total_price = to_float(
            row.get("tprice")
        )

        if total_price is None or total_price <= 0:

            continue

        total_price_count += 1

        # ----------------------------------------------------
        # 建物面積
        #
        # farea = 建物移轉總面積
        # ----------------------------------------------------

        area = to_float(
            row.get("farea")
        )

        # ----------------------------------------------------
        # 如果 farea 沒有資料
        #
        # 使用：
        #
        # 面積 ≈ 總價 ÷ 單價
        #
        # 例如：
        #
        # 1000 萬 ÷ 50 萬/坪
        # = 20 坪
        #
        # 這只作為備援。
        # ----------------------------------------------------

        if area is None or area <= 0:

            calculated_area = total_price / unit_price

            if calculated_area > 0:

                area = calculated_area

            else:

                continue

        area_count += 1

        # ----------------------------------------------------
        # 保存有效資料
        # ----------------------------------------------------

        district_records.append({

            "row": row,

            "unit_price": unit_price,

            "total_price": total_price,

            "area": area,

        })

    # ========================================================
    # 輸出篩選過程
    # ========================================================

    print()
    print("=" * 60)
    print(f"{district} 資料篩選")
    print("=" * 60)

    print(
        f"行政區原始資料：{district_count:,} 筆"
    )

    print(
        f"買賣交易：{sale_count:,} 筆"
    )

    print(
        f"有有效單價：{unit_price_count:,} 筆"
    )

    print(
        f"有有效總價：{total_price_count:,} 筆"
    )

    print(
        f"有有效建物面積：{area_count:,} 筆"
    )

    print(
        f"最後有效住宅買賣：{len(district_records):,} 筆"
    )

    # ========================================================
    # 沒有資料
    # ========================================================

    if not district_records:

        print()
        print(
            f"⚠️ {district} 沒有可分析的住宅買賣資料。"
        )

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
    # 房價分析
    # ========================================================

    print()
    print("=" * 60)
    print(f"{district} 房價分析")
    print("=" * 60)

    # --------------------------------------------------------
    # 有效交易筆數
    # --------------------------------------------------------

    print(
        f"有效住宅買賣筆數："
        f"{len(district_records):,} 筆"
    )

    # --------------------------------------------------------
    # 平均單價
    # --------------------------------------------------------

    print(
        f"平均單價："
        f"{mean(unit_prices):,.2f} 萬元/坪"
    )

    # --------------------------------------------------------
    # 中位數單價
    # --------------------------------------------------------

    print(
        f"中位數單價："
        f"{median(unit_prices):,.2f} 萬元/坪"
    )

    # --------------------------------------------------------
    # 最高單價
    # --------------------------------------------------------

    print(
        f"最高單價："
        f"{max(unit_prices):,.2f} 萬元/坪"
    )

    # --------------------------------------------------------
    # 最低單價
    # --------------------------------------------------------

    print(
        f"最低單價："
        f"{min(unit_prices):,.2f} 萬元/坪"
    )

    # --------------------------------------------------------
    # 平均總價
    # --------------------------------------------------------

    if total_prices:

        print(
            f"平均總價："
            f"{mean(total_prices):,.2f} 萬元"
        )

    else:

        print(
            "平均總價：沒有有效資料"
        )

    # --------------------------------------------------------
    # 平均建物面積
    # --------------------------------------------------------

    if areas:

        print(
            f"平均建物面積："
            f"{mean(areas):,.2f} 坪"
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

            building_types.get(
                building_type,
                0
            ) + 1

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
            f"  {building_type}："
            f"{count:,} 筆"
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
        f"  單價："
        f"{highest['unit_price']:,.2f} 萬元/坪"
    )

    print(
        f"  地址："
        f"{highest_row.get('location', '無資料')}"
    )

    print(
        f"  總價："
        f"{highest['total_price']:,.2f} 萬元"
    )

    print(
        f"  面積："
        f"{highest['area']:,.2f} 坪"
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
        f"  單價："
        f"{lowest['unit_price']:,.2f} 萬元/坪"
    )

    print(
        f"  地址："
        f"{lowest_row.get('location', '無資料')}"
    )

    print(
        f"  總價："
        f"{lowest['total_price']:,.2f} 萬元"
    )

    print(
        f"  面積："
        f"{lowest['area']:,.2f} 坪"
    )

    print()
    print("=" * 60)


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 60)
    print("台北市士林區／北投區房市監控系統")
    print("第四階段：住宅買賣房價分析")
    print("=" * 60)

    # ========================================================
    # 讀取資料
    # ========================================================

    records = load_data()

    print()

    print(
        f"讀取到士林區／北投區資料："
        f"{len(records):,} 筆"
    )

    # ========================================================
    # 沒有資料
    # ========================================================

    if not records:

        print(
            "目前沒有可以分析的資料。"
        )

        return

    # ========================================================
    # 分析兩個行政區
    # ========================================================

    for district in sorted(TARGET_DISTRICTS):

        analyze_district(
            records,
            district
        )

    # ========================================================
    # 完成
    # ========================================================

    print()
    print("=" * 60)
    print("房市分析完成")
    print("=" * 60)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":

    main()
