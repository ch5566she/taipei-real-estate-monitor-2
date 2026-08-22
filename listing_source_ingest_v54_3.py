# -*- coding: utf-8 -*-
"""
listing_source_ingest_v54_3.py
房源資料入口閘門。

用途：
- 接收合法取得／人工匯出的房源 CSV
- 標準化欄位
- 僅保留士林區、北投區
- 以 listing_id 去重，重複時保留欄位較完整者
- 缺單價且總價、坪數都有時才計算單價
- 不猜測缺失資料
- 不爬取 591 或其他網站
- 產生 incoming_listings.csv 與 ingest 品質報告

用法：
python listing_source_ingest_v54_3.py [輸入CSV]
預設輸入：data/source_inbox/incoming.csv
輸出：data/incoming_listings.csv
品質報告：data/listing_ingest_quality_v54_3.json
"""

from pathlib import Path
import json
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "data" / "source_inbox" / "incoming.csv"
OUTPUT_PATH = BASE_DIR / "data" / "incoming_listings.csv"
QUALITY_PATH = BASE_DIR / "data" / "listing_ingest_quality_v54_3.json"

TARGET_DISTRICTS = {"士林區", "北投區"}

CANONICAL = [
    "listing_id", "title", "district", "location", "total_price",
    "building_area", "unit_price", "floor", "total_floor", "rooms",
    "age", "building_type", "url", "source", "collected_at"
]

ALIASES = {
    "listing_id": ["listing_id", "id", "591_id", "591_listing_id"],
    "title": ["title", "標題", "物件標題"],
    "district": ["district", "行政區", "區"],
    "location": ["location", "address", "地址", "路段", "地段"],
    "total_price": ["total_price", "price", "總價", "總價(萬)", "總價萬元"],
    "building_area": ["building_area", "area", "坪數", "建物坪數", "權狀坪數", "建坪", "總坪數"],
    "unit_price": ["unit_price", "current_unit_price", "單價", "單價(萬/坪)", "每坪單價"],
    "floor": ["floor", "樓層"],
    "total_floor": ["total_floor", "total_floors", "總樓層"],
    "rooms": ["rooms", "房數", "房"],
    "age": ["age", "屋齡"],
    "building_type": ["building_type", "建物型態", "型態"],
    "url": ["url", "591_url", "網址"],
    "source": ["source", "來源"],
    "collected_at": ["collected_at", "取得時間", "抓取時間"],
}

def numeric(value):
    text = str(value).strip().replace(",", "")
    if not text:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""

def ingest(input_path):
    if not input_path.exists():
        raise FileNotFoundError(f"找不到輸入 CSV：{input_path}")

    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    input_rows = len(df)

    for canonical in CANONICAL:
        if canonical not in df.columns:
            source = next((c for c in ALIASES[canonical] if c in df.columns), None)
            df[canonical] = df[source] if source else ""

    df["district"] = df["district"].astype(str).str.strip()
    df = df[df["district"].isin(TARGET_DISTRICTS)].copy()
    excluded = input_rows - len(df)

    for c in ["total_price", "building_area", "unit_price",
              "rooms", "age", "floor", "total_floor"]:
        df[c] = df[c].map(numeric)

    calculated = 0
    for idx, row in df.iterrows():
        if not str(row["unit_price"]).strip():
            try:
                price = float(row["total_price"])
                area = float(row["building_area"])
                if price > 0 and area > 0:
                    df.at[idx, "unit_price"] = f"{price / area:.2f}"
                    calculated += 1
            except (ValueError, TypeError):
                pass

    df["_completeness"] = df[CANONICAL].astype(str).apply(
        lambda row: sum(bool(x.strip()) for x in row), axis=1
    )
    duplicate_rows = int(df["listing_id"].duplicated(keep=False).sum())
    df = (
        df.sort_values(["listing_id", "_completeness"], ascending=[True, False])
          .drop_duplicates("listing_id", keep="first")
          .drop(columns=["_completeness"])
    )

    def grade(row):
        if not str(row["listing_id"]).strip():
            return "F"
        if not str(row["total_price"]).strip():
            return "E"
        if any(not str(row[c]).strip() for c in ["total_price", "building_area", "unit_price"]):
            return "C"
        return "B"

    df["ingest_quality"] = df.apply(grade, axis=1)

    df[CANONICAL + ["ingest_quality"]].to_csv(
        OUTPUT_PATH, index=False, encoding="utf-8-sig"
    )

    quality = {
        "version": "54.3",
        "processed_at": datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M:%S"),
        "input_file": str(input_path),
        "input_rows": input_rows,
        "output_rows": int(len(df)),
        "excluded_non_target_district_rows": excluded,
        "duplicate_rows_detected": duplicate_rows,
        "calculated_missing_unit_price": calculated,
        "source_counts": df["source"].replace("", "(空白)").value_counts().to_dict(),
        "district_counts": df["district"].value_counts().to_dict(),
        "collected_at_known": int(df["collected_at"].astype(str).str.strip().ne("").sum()),
        "collected_at_unknown": int(df["collected_at"].astype(str).str.strip().eq("").sum()),
        "rule": "只整理合法取得的 CSV；不爬取網站、不猜測缺失資料、不將 processed_at 冒充 collected_at。"
    }
    QUALITY_PATH.write_text(
        json.dumps(quality, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return quality

if __name__ == "__main__":
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    result = ingest(input_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
