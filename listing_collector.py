# -*- coding: utf-8 -*-
"""
第26階段：士林／北投在售案源資料整理器

用途：
1. 讀取 data/raw_listings.csv（或指定的來源 CSV）
2. 標準化欄位
3. 僅保留士林區／北投區
4. 計算缺少的單價（總價 ÷ 坪數）
5. 去除重複物件
6. 輸出乾淨的 data/current_listings.csv

注意：
- 本程式目前是「資料整理層」，不假造即時房源。
- 真正的公開房源來源接入後，只需把來源 CSV 接到本程式即可。
"""

from __future__ import annotations

import csv
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

TARGET_DISTRICTS = {"士林區", "北投區"}

# 第26階段：
# raw_listings.csv = 真實在售房源資料入口
# current_listings.csv = 本程式整理後的標準化輸出
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_LISTINGS_PATH = os.path.join(BASE_DIR, "data", "raw_listings.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "current_listings.csv")

CANONICAL_FIELDS = [
    "listing_id",
    "district",
    "location",
    "title",
    "total_price",
    "building_area",
    "unit_price",
    "age",
    "floor",
    "total_floors",
    "rooms",
    "halls",
    "bathrooms",
    "parking",
    "source",
    "url",
    "status",
    "updated_at",
]

ALIASES = {
    "listing_id": ["listing_id", "id", "物件編號", "案件編號", "編號"],
    "district": ["district", "行政區", "區域", "行政區域"],
    "location": ["location", "路段", "地址", "地段", "street"],
    "title": ["title", "物件名稱", "標題", "社區名稱", "community"],
    "total_price": ["total_price", "總價", "售價", "價格", "price"],
    "building_area": ["building_area", "建物坪數", "坪數", "建坪", "總坪數", "area"],
    "unit_price": ["unit_price", "單價", "每坪", "單價萬坪", "price_per_ping"],
    "age": ["age", "屋齡", "屋齡年數"],
    "floor": ["floor", "樓層", "所在樓層"],
    "total_floors": ["total_floors", "總樓層", "樓高"],
    "rooms": ["rooms", "房", "房數"],
    "halls": ["halls", "廳", "廳數"],
    "bathrooms": ["bathrooms", "衛", "衛浴", "衛浴數"],
    "parking": ["parking", "車位", "停車位"],
    "source": ["source", "來源", "平台"],
    "url": ["url", "網址", "連結", "物件網址"],
    "status": ["status", "狀態"],
    "updated_at": ["updated_at", "更新時間", "資料時間"],
}


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def normalize_district(value):
    text = clean_text(value)
    text = text.replace("台北市", "").replace("臺北市", "")
    text = text.replace("士林", "士林區") if text == "士林" else text
    text = text.replace("北投", "北投區") if text == "北投" else text
    return text


def parse_number(value):
    """把 3,200 萬、3.2、83.5坪 等常見格式轉成 float。"""
    text = clean_text(value)
    if not text:
        return None

    text = text.replace(",", "").replace("，", "")
    text = text.replace("萬", "").replace("萬元", "")
    text = text.replace("坪", "").replace("㎡", "").replace("平方公尺", "")
    text = text.replace("約", "").strip()

    # 取第一個數字，避免「6/12樓」整段無法解析
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    try:
        return float(match.group(0))
    except ValueError:
        return None


def find_value(row, field):
    for key in ALIASES[field]:
        if key in row and clean_text(row[key]) != "":
            return row[key]
    return ""


def normalize_price(value):
    number = parse_number(value)
    if number is None:
        return None
    return round(number, 2)


def normalize_area(value):
    number = parse_number(value)
    if number is None or number <= 0:
        return None
    return round(number, 2)


def normalize_unit_price(value):
    number = parse_number(value)
    if number is None or number <= 0:
        return None
    return round(number, 2)


def normalize_row(row, index):
    district = normalize_district(find_value(row, "district"))
    total_price = normalize_price(find_value(row, "total_price"))
    area = normalize_area(find_value(row, "building_area"))
    unit_price = normalize_unit_price(find_value(row, "unit_price"))

    # 若沒有單價，且總價為「萬元」、坪數存在，直接計算。
    if unit_price is None and total_price is not None and area:
        unit_price = round(total_price / area, 2)

    listing_id = clean_text(find_value(row, "listing_id"))
    if not listing_id:
        location = clean_text(find_value(row, "location"))
        title = clean_text(find_value(row, "title"))
        listing_id = f"AUTO-{index:05d}-{district}-{location}-{title}"

    normalized = {
        "listing_id": listing_id,
        "district": district,
        "location": clean_text(find_value(row, "location")),
        "title": clean_text(find_value(row, "title")),
        "total_price": total_price if total_price is not None else "",
        "building_area": area if area is not None else "",
        "unit_price": unit_price if unit_price is not None else "",
        "age": clean_text(find_value(row, "age")),
        "floor": clean_text(find_value(row, "floor")),
        "total_floors": clean_text(find_value(row, "total_floors")),
        "rooms": clean_text(find_value(row, "rooms")),
        "halls": clean_text(find_value(row, "halls")),
        "bathrooms": clean_text(find_value(row, "bathrooms")),
        "parking": clean_text(find_value(row, "parking")),
        "source": clean_text(find_value(row, "source")) or "unknown",
        "url": clean_text(find_value(row, "url")),
        "status": clean_text(find_value(row, "status")) or "active",
        "updated_at": clean_text(find_value(row, "updated_at")),
    }

    return normalized


def read_csv(path):
    if not os.path.exists(path):
        return []

    # utf-8-sig 可處理 Excel 常見 BOM
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def deduplicate(rows):
    seen = set()
    result = []

    for row in rows:
        key = clean_text(row.get("listing_id"))
        if not key:
            key = "|".join([
                clean_text(row.get("district")),
                clean_text(row.get("location")),
                clean_text(row.get("title")),
                clean_text(row.get("total_price")),
                clean_text(row.get("building_area")),
            ])

        if key in seen:
            continue

        seen.add(key)
        result.append(row)

    return result


def collect(source_path=RAW_LISTINGS_PATH, output_path=OUTPUT_PATH):
    """
    將真實在售房源入口 CSV 標準化為 current_listings.csv。

    第26階段的重要規則：
    1. 預設來源是 data/raw_listings.csv。
    2. 不再把 current_listings.csv 當成自己的來源。
    3. 來源不存在或沒有有效士林／北投資料時，不產生假資料。
    4. 不自動保留 TEST001 / TEST002 等測試物件。
    """
    source_path = os.path.abspath(source_path)
    output_path = os.path.abspath(output_path)

    if not os.path.exists(source_path):
        print("=" * 70)
        print("⚠️ 今日沒有取得真實在售房源資料")
        print(f"找不到資料來源：{source_path}")
        print("請將真實公開房源資料放入 data/raw_listings.csv")
        print("=" * 70)

        # 不用舊 current_listings.csv 冒充今日資料。
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
                print(f"已移除舊的在售資料：{output_path}")
            except OSError as exc:
                print(f"⚠️ 無法移除舊資料：{exc}")

        return []

    raw_rows = read_csv(source_path)

    if not raw_rows:
        print("=" * 70)
        print("⚠️ 今日沒有取得真實在售房源資料")
        print(f"資料來源為空：{source_path}")
        print("=" * 70)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass

        return []

    normalized = []

    for index, row in enumerate(raw_rows, start=1):
        item = normalize_row(row, index)

        # 不讓測試物件進入正式每日資料。
        listing_id = clean_text(item.get("listing_id"))
        source = clean_text(item.get("source"))

        if listing_id.upper().startswith("TEST"):
            continue

        if source.lower() == "manual" and listing_id.upper().startswith("TEST"):
            continue

        if item["district"] not in TARGET_DISTRICTS:
            continue

        # 至少要有物件名稱/位置與價格或坪數中的基本資料。
        if not item["location"] and not item["title"]:
            continue

        if not item["total_price"] and not item["unit_price"]:
            continue

        normalized.append(item)

    normalized = deduplicate(normalized)

    if not normalized:
        print("=" * 70)
        print("⚠️ 今日沒有取得有效的士林／北投真實在售房源資料")
        print(f"來源：{source_path}")
        print("請確認 raw_listings.csv 包含有效房源及價格資料。")
        print("=" * 70)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass

        return []

    now = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S")

    for item in normalized:
        if not item["updated_at"]:
            item["updated_at"] = now

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CANONICAL_FIELDS)
        writer.writeheader()
        writer.writerows(normalized)

    return normalized


def main():
    source = (
        os.path.abspath(sys.argv[1])
        if len(sys.argv) >= 2
        else RAW_LISTINGS_PATH
    )

    output = (
        os.path.abspath(sys.argv[2])
        if len(sys.argv) >= 3
        else OUTPUT_PATH
    )

    rows = collect(source, output)

    print("=" * 70)
    print("第26階段：在售案源資料整理完成")
    print("=" * 70)
    print(f"來源：{source}")
    print(f"輸出：{output}")
    print(f"士林／北投有效真實在售資料：{len(rows):,} 筆")

    district_counts = {}

    for row in rows:
        district = row["district"]
        district_counts[district] = district_counts.get(district, 0) + 1

    for district in sorted(TARGET_DISTRICTS):
        print(f"  {district}：{district_counts.get(district, 0):,} 筆")

    if not rows:
        print()
        print("⚠️ 本次沒有真實在售房源。")
        print("⚠️ 不會使用舊 current_listings.csv 或 TEST001/TEST002 冒充今日資料。")

    print("=" * 70)


if __name__ == "__main__":
    main()
