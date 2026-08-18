# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統

第四階段：住宅買賣房價分析

功能：
1. 讀取 data/taipei_transactions.csv
2. 只分析士林區、北投區
3. 只分析「買賣」
4. 只分析住宅類型
5. 自動抓取單價 pu_area
6. 排除空白、0、無效單價
7. 計算：
   - 成交筆數
   - 平均單價
   - 中位數單價
   - 最高單價
   - 最低單價
   - 平均總價
   - 平均建物面積
8. 統計住宅類型
9. 顯示最高／最低單價案例
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
    value = value.replace(" ", "")

    try:
        return float(value)
    except ValueError:
        return None


# ============================================================
# 讀取資料
# ============================================================

def load_data():
    """
    讀取實價登錄 CSV。
    只保留士林區、北投區。
    """

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

        # 顯示 CSV 欄位
        fieldnames = reader.fieldnames or []

        print(f"資料欄位數：{len(fieldnames)}")

        print("資料欄位：")
        print(", ".join(fieldnames))

        for row in reader:

            district = str(
                row.get("district", "")
            ).strip()

            if district not in TARGET_DISTRICTS:
                continue

            records.append(row)

    return records


# ============================================================
# 找單價欄位
# ============================================================

def get_unit_price(row):
    """
    取得單價。

    優先使用：
    1. pu_area

    如果未來資料欄位名稱改變，
    再嘗試其他可能欄位。
    """

    possible_fields = [
        "pu_area",
        "uprice",
        "unit_price",
        "unitprice",
    ]

    for field in possible_fields:

        value = to_float(
            row.get(field)
        )

        if value is not None and value > 0:
            return value

    return None


# ============================================================
# 房屋分析
# ============================================================

def analyze_district(records, district):
    """
    分析指定行政區。
    """

    district_records = []

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
        # ====================================================

        unit_price = get_unit_price(row)

        if unit_price is None or unit_price <= 0:
            continue

        # ====================================================
        # 總價
        # ====================================================

        total_price = to_float(
            row.get("price")
        )

        # ====================================================
        # 建物面積
        # ====================================================

        area = to_float(
            row.get("area")
        )

        district_records.append({
            "row": row,
            "unit_price": unit_price,
            "total_price": total_price,
            "area": area,
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
        if item["unit_price"] is not None
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
    # 顯示標題
    # ========================================================

    print()
    print("=" * 60)
    print(f"{district} 房價分析")
    print("=" * 60)

    print(
        f"有效買賣筆數：{len(district_records):,} 筆"
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
            f"平均總價：{mean(total_prices):.2f} 萬元"
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
        f"  總價：{highest_row.get('price', '無資料')} 萬元"
    )

    print(
        f"  面積：{highest_row.get('area', '無資料')} 坪"
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
        f"  總價：{lowest_row.get('price', '無資料')} 萬元"
    )

    print(
        f"  面積：{lowest_row.get('area', '無資料')} 坪"
    )


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 60)
    print("台北市士林區／北投區房市監控系統")
    print("第四階段：住宅買賣房價分析")
    print("=" * 60)

    records = load_data()

    print()
    print(
        f"讀取到士林區／北投區資料：{len(records):,} 筆"
    )

    if not records:

        print("目前沒有可以分析的資料。")
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
