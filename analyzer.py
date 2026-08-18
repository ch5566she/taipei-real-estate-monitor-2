# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市分析程式
第二階段：交易資料統計分析
"""

import csv
import os
from statistics import mean, median


INPUT_FILE = "data/taipei_transactions.csv"

TARGET_DISTRICTS = {
    "士林區",
    "北投區",
}


def to_float(value):
    """把文字轉成數字，無法轉換時回傳 None。"""

    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def load_data():
    """讀取交易資料。"""

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

        for row in reader:

            district = str(
                row.get("district", "")
            ).strip()

            if district not in TARGET_DISTRICTS:
                continue

            records.append(row)

    return records


def analyze_district(records, district):
    """分析指定行政區。"""

    district_records = []

    for row in records:

        if str(row.get("district", "")).strip() != district:
            continue

        # 單價欄位
        unit_price = to_float(
            row.get("UPRICE")
        )

        # 排除沒有單價或單價為 0 的資料
        if unit_price is None or unit_price <= 0:
            continue

        district_records.append(
            unit_price
        )

    if not district_records:
        print(f"\n{district}")
        print("沒有可分析的住宅單價資料。")
        return

    print()
    print("=" * 60)
    print(f"{district} 房價分析")
    print("=" * 60)

    print(f"有效交易筆數：{len(district_records):,} 筆")

    print(
        f"平均單價：{mean(district_records):,.2f} 萬元/坪"
    )

    print(
        f"中位數單價：{median(district_records):,.2f} 萬元/坪"
    )

    print(
        f"最高單價：{max(district_records):,.2f} 萬元/坪"
    )

    print(
        f"最低單價：{min(district_records):,.2f} 萬元/坪"
    )


def main():

    print("=" * 60)
    print("台北市士林區／北投區房市分析系統")
    print("第二階段：交易資料統計分析")
    print("=" * 60)

    records = load_data()

    print(
        f"\n讀取到士林區／北投區資料：{len(records):,} 筆"
    )

    if not records:
        print("目前沒有可分析的資料。")
        return

    for district in sorted(TARGET_DISTRICTS):

        analyze_district(
            records,
            district
        )

    print()
    print("=" * 60)
    print("房市分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
