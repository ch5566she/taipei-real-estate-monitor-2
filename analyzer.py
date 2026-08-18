# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第四階段：住宅買賣房價分析

功能：
1. 讀取 data/taipei_transactions.csv
2. 只分析士林區、北投區
3. 只分析「買賣」
4. 排除純土地交易
5. 使用官方 UPRICE 作為交易單價
6. UPRICE 沒有資料時，用總價 ÷ 建物面積計算
7. 計算平均單價
8. 計算中位數單價
9. 計算最高單價
10. 計算最低單價
11. 計算平均總價
12. 計算平均建物坪數
13. 統計住宅型態
14. 顯示最高／最低單價代表案例
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
    將文字轉成數字。
    無法轉換時回傳 None。
    """

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    # 移除常見符號
    value = value.replace(",", "")
    value = value.replace("，", "")
    value = value.replace(" ", "")

    try:
        return float(value)

    except (ValueError, TypeError):
        return None


# ============================================================
# 取得欄位
# ============================================================

def get_value(row, *field_names):
    """
    依序尋找欄位。

    例如：
    get_value(row, "uprice", "UPRICE")
    """

    for field_name in field_names:

        if field_name in row:

            value = row.get(field_name)

            if value is not None and str(value).strip() != "":
                return value

    return None


# ============================================================
# 讀取資料
# ============================================================

def load_data():

    print()
    print("=" * 60)
    print("讀取房市資料")
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

        for row in reader:

            # ------------------------------------------------
            # 行政區
            # ------------------------------------------------

            district = str(
                get_value(
                    row,
                    "district",
                    "DISTRICT"
                ) or ""
            ).strip()

            if district not in TARGET_DISTRICTS:
                continue

            records.append(row)

    return records


# ============================================================
# 房價分析
# ============================================================

def analyze_district(records, district):

    print()
    print("=" * 60)
    print(f"{district} 房價分析")
    print("=" * 60)

    district_records = []

    # ========================================================
    # 篩選資料
    # ========================================================

    for row in records:

        # ----------------------------------------------------
        # 行政區
        # ----------------------------------------------------

        row_district = str(
            get_value(
                row,
                "district",
                "DISTRICT"
            ) or ""
        ).strip()

        if row_district != district:
            continue

        # ----------------------------------------------------
        # 只分析「買賣」
        # ----------------------------------------------------

        case_type = str(
            get_value(
                row,
                "case_t",
                "CASE_T"
            ) or ""
        ).strip()

        if case_type != "買賣":
            continue

        # ----------------------------------------------------
        # 交易標的
        # ----------------------------------------------------

        case_target = str(
            get_value(
                row,
                "case_f",
                "CASE_F"
            ) or ""
        ).strip()

        # ----------------------------------------------------
        # 排除純土地
        #
        # 住宅房屋交易通常會包含：
        # 房屋
        # 房屋+車位
        # 土地+房屋
        # 土地+房屋+車位
        #
        # 只要沒有「房屋」字樣，就不列入住宅房價分析。
        # ----------------------------------------------------

        if "房屋" not in case_target:

            continue

        # ----------------------------------------------------
        # 交易單價
        #
        # UPRICE = 交易單價（萬元/坪）
        # ----------------------------------------------------

        unit_price = to_float(
            get_value(
                row,
                "uprice",
                "UPRICE"
            )
        )

        # ----------------------------------------------------
        # 如果官方單價沒有資料
        # 嘗試使用：
        #
        # 總價 ÷ 建物面積
        # ----------------------------------------------------

        total_price = to_float(
            get_value(
                row,
                "price",
                "tprice",
                "TPRICE"
            )
        )

        area = to_float(
            get_value(
                row,
                "area",
                "farea",
                "FAREA"
            )
        )

        if unit_price is None or unit_price <= 0:

            if (
                total_price is not None
                and total_price > 0
                and area is not None
                and area > 0
            ):

                unit_price = total_price / area

            else:

                continue

        # ----------------------------------------------------
        # 基本合理性檢查
        # ----------------------------------------------------

        if unit_price <= 0:

            continue

        # 避免極端錯誤資料影響統計
        #
        # 這裡不是說超過 200 萬就一定錯，
        # 而是避免資料單位錯誤造成平均值失真。
        #
        # 臺北市住宅一般情況下遠低於此範圍。
        # ----------------------------------------------------

        if unit_price > 200:

            continue

        # ----------------------------------------------------
        # 儲存
        # ----------------------------------------------------

        district_records.append(
            {
                "row": row,
                "unit_price": unit_price,
                "total_price": total_price,
                "area": area,
                "case_target": case_target,
            }
        )

    # ========================================================
    # 沒有資料
    # ========================================================

    if not district_records:

        print()
        print("沒有可分析的住宅買賣資料。")
        print()
        return

    # ========================================================
    # 基本統計
    # ========================================================

    unit_prices = [
        item["unit_price"]
        for item in district_records
        if item["unit_price"] is not None
    ]

    total_prices = [
        item["total_price"]
        for item in district_records
        if (
            item["total_price"] is not None
            and item["total_price"] > 0
        )
    ]

    areas = [
        item["area"]
        for item in district_records
        if (
            item["area"] is not None
            and item["area"] > 0
        )
    ]

    # ========================================================
    # 標題
    # ========================================================

    print()
    print("-" * 60)
    print(f"{district} 住宅房價分析")
    print("-" * 60)

    # ========================================================
    # 交易筆數
    # ========================================================

    print(
        f"有效住宅買賣筆數：{len(district_records):,} 筆"
    )

    # ========================================================
    # 平均單價
    # ========================================================

    print(
        f"平均單價：{mean(unit_prices):,.2f} 萬元/坪"
    )

    # ========================================================
    # 中位數
    # ========================================================

    print(
        f"中位數單價：{median(unit_prices):,.2f} 萬元/坪"
    )

    # ========================================================
    # 最高單價
    # ========================================================

    print(
        f"最高單價：{max(unit_prices):,.2f} 萬元/坪"
    )

    # ========================================================
    # 最低單價
    # ========================================================

    print(
        f"最低單價：{min(unit_prices):,.2f} 萬元/坪"
    )

    # ========================================================
    # 平均總價
    # ========================================================

    if total_prices:

        print(
            f"平均交易總價：{mean(total_prices):,.2f} 萬元"
        )

    else:

        print("平均交易總價：沒有有效資料")

    # ========================================================
    # 平均坪數
    # ========================================================

    if areas:

        print(
            f"平均建物面積：{mean(areas):,.2f} 坪"
        )

    else:

        print("平均建物面積：沒有有效資料")

    # ========================================================
    # 住宅型態統計
    # ========================================================

    print()
    print("-" * 60)
    print("住宅型態統計")
    print("-" * 60)

    building_types = {}

    for item in district_records:

        row = item["row"]

        building_type = str(
            get_value(
                row,
                "buitype",
                "BUITYPE"
            ) or ""
        ).strip()

        if building_type == "":
            building_type = "其他"

        building_types[building_type] = (
            building_types.get(
                building_type,
                0
            ) + 1
        )

    sorted_types = sorted(
        building_types.items(),
        key=lambda x: x[1],
        reverse=True
    )

    for building_type, count in sorted_types:

        print(
            f"{building_type}：{count:,} 筆"
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
    print("-" * 60)
    print("最高單價代表案例")
    print("-" * 60)

    print(
        f"單價：{highest['unit_price']:,.2f} 萬元/坪"
    )

    print(
        "地址："
        f"{get_value(highest_row, 'location', 'LOCATION') or '無資料'}"
    )

    print(
        "總價："
        f"{get_value(highest_row, 'price', 'tprice', 'TPRICE') or '無資料'} 萬元"
    )

    print(
        "面積："
        f"{get_value(highest_row, 'area', 'farea', 'FAREA') or '無資料'} 坪"
    )

    print(
        "屋齡／建築完成年月："
        f"{get_value(highest_row, 'fdate', 'FDATE') or '無資料'}"
    )

    print(
        "建物型態："
        f"{get_value(highest_row, 'buitype', 'BUITYPE') or '無資料'}"
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
    print("-" * 60)
    print("最低單價代表案例")
    print("-" * 60)

    print(
        f"單價：{lowest['unit_price']:,.2f} 萬元/坪"
    )

    print(
        "地址："
        f"{get_value(lowest_row, 'location', 'LOCATION') or '無資料'}"
    )

    print(
        "總價："
        f"{get_value(lowest_row, 'price', 'tprice', 'TPRICE') or '無資料'} 萬元"
    )

    print(
        "面積："
        f"{get_value(lowest_row, 'area', 'farea', 'FAREA') or '無資料'} 坪"
    )

    print(
        "屋齡／建築完成年月："
        f"{get_value(lowest_row, 'fdate', 'FDATE') or '無資料'}"
    )

    print(
        "建物型態："
        f"{get_value(lowest_row, 'buitype', 'BUITYPE') or '無資料'}"
    )

    # ========================================================
    # 完成
    # ========================================================

    print()
    print("-" * 60)


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 60)
    print("台北市士林區／北投區房市監控系統")
    print("第四階段：住宅買賣房價分析")
    print("=" * 60)

    # --------------------------------------------------------
    # 讀取資料
    # --------------------------------------------------------

    records = load_data()

    print()
    print(
        f"讀取到士林區／北投區資料：{len(records):,} 筆"
    )

    if not records:

        print()
        print("目前沒有可以分析的資料。")

        return

    # --------------------------------------------------------
    # 分析兩個行政區
    # --------------------------------------------------------

    for district in sorted(TARGET_DISTRICTS):

        analyze_district(
            records,
            district
        )

    # --------------------------------------------------------
    # 完成
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("房市分析完成")
    print("=" * 60)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":

    main()
