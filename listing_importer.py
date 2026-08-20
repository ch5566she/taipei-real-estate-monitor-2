# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第30階段：在售房源資料匯入器

用途：
1. 讀取 data/incoming_listings.csv
2. 篩選士林區、北投區
3. 標準化房源欄位
4. 自動計算缺少的單價
5. 去除重複房源
6. 輸出 data/raw_listings.csv

注意：
本程式不負責爬取網站。
incoming_listings.csv 必須來自合法取得或人工匯出的資料。
"""

import csv
import os
import re
from datetime import datetime, timezone, timedelta


INPUT_FILE = "data/incoming_listings.csv"
OUTPUT_FILE = "data/raw_listings.csv"

TARGET_DISTRICTS = {
    "士林區",
    "北投區",
}


# ============================================================
# 基本工具
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def parse_number(value):
    """
    將：
    2,988
    2,988.50
    2988萬
    27.54坪

    等文字轉成數字。
    """

    if value is None:
        return None

    text = clean_text(value)

    if not text:
        return None

    text = text.replace(",", "")
    text = text.replace("，", "")

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def format_number(value):
    """
    將數字轉成適合 CSV 的格式。
    """

    if value is None:
        return ""

    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))

        return f"{number:.2f}".rstrip("0").rstrip(".")

    except (ValueError, TypeError):
        return str(value)


# ============================================================
# 欄位名稱標準化
# ============================================================

FIELD_ALIASES = {

    "listing_id": [
        "listing_id",
        "id",
        "物件編號",
        "案件編號",
        "房屋編號",
    ],

    "title": [
        "title",
        "name",
        "物件名稱",
        "標題",
        "房屋名稱",
    ],

    "district": [
        "district",
        "行政區",
        "區",
        "區域",
    ],

    "location": [
        "location",
        "address",
        "地址",
        "路段",
        "位置",
    ],

    "total_price": [
        "total_price",
        "price",
        "總價",
        "售價",
        "房屋總價",
    ],

    "building_area": [
        "building_area",
        "area",
        "坪數",
        "建物坪數",
        "建坪",
        "總坪數",
    ],

    "unit_price": [
        "unit_price",
        "單價",
        "每坪單價",
        "單坪價格",
    ],

    "floor": [
        "floor",
        "樓層",
        "所在樓層",
    ],

    "total_floor": [
        "total_floor",
        "總樓層",
        "總樓層數",
    ],

    "rooms": [
        "rooms",
        "room",
        "房",
        "房數",
    ],

    "age": [
        "age",
        "屋齡",
    ],

    "building_type": [
        "building_type",
        "建物類型",
        "型態",
        "房屋型態",
    ],

    "url": [
        "url",
        "link",
        "網址",
        "物件網址",
        "連結",
    ],

    "source": [
        "source",
        "來源",
        "資料來源",
    ],
}


def find_column(row, aliases):
    """
    找出輸入 CSV 中對應的欄位。
    """

    for alias in aliases:

        if alias in row:
            return clean_text(row.get(alias))

    return ""


# ============================================================
# 標準化單筆房源
# ============================================================

def normalize_listing(row, index):

    district = find_column(
        row,
        FIELD_ALIASES["district"]
    )

    # ----------------------------------------
    # 行政區判斷
    # ----------------------------------------

    if district not in TARGET_DISTRICTS:

        # 有些資料可能把地址寫在 location
        location = find_column(
            row,
            FIELD_ALIASES["location"]
        )

        if "士林區" in location:
            district = "士林區"

        elif "北投區" in location:
            district = "北投區"

        else:
            return None

    # ----------------------------------------
    # 基本欄位
    # ----------------------------------------

    listing_id = find_column(
        row,
        FIELD_ALIASES["listing_id"]
    )

    title = find_column(
        row,
        FIELD_ALIASES["title"]
    )

    location = find_column(
        row,
        FIELD_ALIASES["location"]
    )

    # ----------------------------------------
    # 價格
    # ----------------------------------------

    total_price = parse_number(
        find_column(
            row,
            FIELD_ALIASES["total_price"]
        )
    )

    building_area = parse_number(
        find_column(
            row,
            FIELD_ALIASES["building_area"]
        )
    )

    unit_price = parse_number(
        find_column(
            row,
            FIELD_ALIASES["unit_price"]
        )
    )

    # ----------------------------------------
    # 如果沒有物件編號
    # ----------------------------------------

    if not listing_id:

        listing_id = (
            f"IMPORT-"
            f"{district}-"
            f"{index:06d}"
        )

    # ----------------------------------------
    # 如果沒有單價，自動計算
    #
    # 總價單位：萬元
    # 坪數：坪
    # ----------------------------------------

    if (
        unit_price is None
        and total_price is not None
        and building_area
        and building_area > 0
    ):

        unit_price = (
            total_price / building_area
        )

    # ----------------------------------------
    # 其他欄位
    # ----------------------------------------

    floor = find_column(
        row,
        FIELD_ALIASES["floor"]
    )

    total_floor = find_column(
        row,
        FIELD_ALIASES["total_floor"]
    )

    rooms = find_column(
        row,
        FIELD_ALIASES["rooms"]
    )

    age = find_column(
        row,
        FIELD_ALIASES["age"]
    )

    building_type = find_column(
        row,
        FIELD_ALIASES["building_type"]
    )

    url = find_column(
        row,
        FIELD_ALIASES["url"]
    )

    source = find_column(
        row,
        FIELD_ALIASES["source"]
    )

    if not source:
        source = "合法匯入資料"

    # ----------------------------------------
    # 台灣時間
    # ----------------------------------------

    taiwan_timezone = timezone(
        timedelta(hours=8)
    )

    collected_at = datetime.now(
        taiwan_timezone
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    # ----------------------------------------
    # 輸出標準格式
    # ----------------------------------------

    return {

        "listing_id": listing_id,

        "title": title,

        "district": district,

        "location": location,

        "total_price": format_number(
            total_price
        ),

        "building_area": format_number(
            building_area
        ),

        "unit_price": format_number(
            unit_price
        ),

        "floor": floor,

        "total_floor": total_floor,

        "rooms": rooms,

        "age": age,

        "building_type": building_type,

        "url": url,

        "source": source,

        "collected_at": collected_at,
    }


# ============================================================
# 讀取 CSV
# ============================================================

def load_input():

    if not os.path.exists(INPUT_FILE):

        print()
        print("=" * 60)
        print("找不到房源匯入檔案")
        print(f"請將合法取得的房源 CSV 放到：")
        print(INPUT_FILE)
        print("=" * 60)

        return []

    records = []

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as csvfile:

        reader = csv.DictReader(csvfile)

        for index, row in enumerate(
            reader,
            start=1
        ):

            normalized = normalize_listing(
                row,
                index
            )

            if normalized:
                records.append(
                    normalized
                )

    return records


# ============================================================
# 去除重複
# ============================================================

def remove_duplicates(records):

    unique = {}

    for record in records:

        key = record.get(
            "listing_id",
            ""
        ).strip()

        if not key:

            key = "|".join([
                record.get("district", ""),
                record.get("location", ""),
                record.get("title", ""),
                record.get("total_price", ""),
            ])

        unique[key] = record

    return list(unique.values())


# ============================================================
# 保存 CSV
# ============================================================

def save_output(records):

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    fieldnames = [
        "listing_id",
        "title",
        "district",
        "location",
        "total_price",
        "building_area",
        "unit_price",
        "floor",
        "total_floor",
        "rooms",
        "age",
        "building_type",
        "url",
        "source",
        "collected_at",
    ]

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()

        writer.writerows(records)

    print()
    print("=" * 60)
    print("房源資料匯入完成")
    print(f"輸出檔案：{OUTPUT_FILE}")
    print(f"房源筆數：{len(records)}")
    print("=" * 60)


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 60)
    print("台北市士林區／北投區房市監控系統")
    print("第30階段：在售房源資料匯入")
    print("=" * 60)

    records = load_input()

    if not records:

        print()
        print("目前沒有可匯入的房源資料。")
        print("不會建立假資料。")
        return

    records = remove_duplicates(
        records
    )

    # ----------------------------------------
    # 統計
    # ----------------------------------------

    shilin_count = sum(
        1
        for r in records
        if r["district"] == "士林區"
    )

    beitou_count = sum(
        1
        for r in records
        if r["district"] == "北投區"
    )

    print()
    print(f"士林區：{shilin_count} 筆")
    print(f"北投區：{beitou_count} 筆")
    print(f"合計：{len(records)} 筆")

    save_output(records)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
