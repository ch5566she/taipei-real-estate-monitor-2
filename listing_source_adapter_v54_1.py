# -*- coding: utf-8 -*-
"""
房源資料來源 Adapter V54.1
用途：
1. 讀取 data/incoming_listings.csv
2. 標準化核心房源欄位
3. 缺少單價時，以「總價(萬元) / 建物坪數」計算
4. 不猜測缺失資料
5. 產生驗證後 CSV 與資料品質 JSON

注意：本模組不負責抓取 591 網站。
"""

from pathlib import Path
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
INPUT_PATH = BASE_DIR / "data" / "incoming_listings.csv"
OUTPUT_PATH = BASE_DIR / "data" / "incoming_listings_validated.csv"
QUALITY_PATH = BASE_DIR / "data" / "listing_source_quality.json"

CORE = ["listing_id", "district", "total_price", "building_area", "unit_price"]
SUPPLEMENTAL = [
    "location", "floor", "total_floors", "rooms",
    "age", "building_type", "url"
]

ALIASES = {
    "listing_id": ["listing_id", "id", "591_id", "591_listing_id"],
    "district": ["district", "行政區", "區"],
    "title": ["title", "標題", "物件標題"],
    "total_price": ["total_price", "price", "總價", "總價(萬)", "總價萬元"],
    "building_area": [
        "building_area", "area", "farea", "坪數", "建物坪數",
        "權狀坪數", "主建物坪數", "建坪", "總坪數"
    ],
    "unit_price": [
        "unit_price", "current_unit_price", "單價",
        "單價(萬/坪)", "每坪單價"
    ],
    "location": ["location", "address", "地址", "路段", "地段"],
    "floor": ["floor", "樓層"],
    "total_floors": ["total_floors", "total_floor", "總樓層"],
    "rooms": ["rooms", "房數", "房"],
    "halls": ["halls", "廳數", "廳"],
    "bathrooms": ["bathrooms", "衛數", "衛"],
    "age": ["age", "屋齡"],
    "building_type": ["building_type", "建物型態", "型態"],
    "url": ["url", "591_url", "網址"],
    "source": ["source", "來源"],
    "collected_at": ["collected_at", "取得時間", "抓取時間"],
}

def clean_num(value):
    text = str(value).strip().replace(",", "")
    if not text:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""

def first_existing(columns, candidates):
    for name in candidates:
        if name in columns:
            return name
    return None

def run():
    df = pd.read_csv(INPUT_PATH, dtype=str, keep_default_na=False)

    for canonical, candidates in ALIASES.items():
        if canonical not in df.columns:
            source_col = first_existing(df.columns, candidates)
            df[canonical] = df[source_col] if source_col else ""

    for col in [
        "total_price", "building_area", "unit_price",
        "rooms", "halls", "bathrooms", "age",
        "floor", "total_floors"
    ]:
        df[col] = df[col].map(clean_num)

    for idx, row in df.iterrows():
        if not str(row["unit_price"]).strip():
            try:
                price = float(row["total_price"])
                area = float(row["building_area"])
                if price > 0 and area > 0:
                    df.at[idx, "unit_price"] = f"{price / area:.2f}"
            except (ValueError, TypeError):
                pass

    grades, missing, core_missing, formal, reasons = [], [], [], [], []

    for _, row in df.iterrows():
        miss = [
            c for c in CORE + SUPPLEMENTAL
            if not str(row.get(c, "")).strip()
        ]
        cm = [
            c for c in CORE
            if not str(row.get(c, "")).strip()
        ]

        if not str(row["listing_id"]).strip():
            grade = "F"
        elif not str(row["total_price"]).strip():
            grade = "E"
        elif cm:
            grade = "D"
        elif miss:
            grade = "C"
        else:
            grade = "B"

        grades.append(grade)
        missing.append(",".join(miss))
        core_missing.append(",".join(cm))
        formal.append("YES" if not cm else "NO")

        if cm:
            reasons.append("核心價格欄位缺失：" + ",".join(cm))
        elif miss:
            reasons.append("核心價格欄位完整；補充欄位缺失：" + ",".join(miss))
        else:
            reasons.append("核心與主要補充欄位完整")

    df["data_quality_grade"] = grades
    df["missing_fields"] = missing
    df["core_missing_fields"] = core_missing
    df["can_formal_pricing"] = formal
    df["quality_reason"] = reasons
    df["processed_at"] = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).strftime("%Y-%m-%d %H:%M:%S")

    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    quality = {
        "source_file": str(INPUT_PATH.relative_to(BASE_DIR)),
        "processed_at": df["processed_at"].iloc[0] if len(df) else "",
        "total_listings": int(len(df)),
        "quality_grade_counts": df["data_quality_grade"].value_counts().sort_index().to_dict(),
        "core_complete": int((df["core_missing_fields"] == "").sum()),
        "formal_pricing_candidates": int(
            (df["can_formal_pricing"] == "YES").sum()
        ),
        "field_completeness": {
            c: {
                "present": int(df[c].astype(str).str.strip().ne("").sum()),
                "total": int(len(df)),
                "rate": round(
                    float(df[c].astype(str).str.strip().ne("").mean()), 4
                ) if len(df) else 0
            }
            for c in CORE + SUPPLEMENTAL
        },
        "source_note": "測試用資料品質驗證；不補猜缺失欄位。"
    }

    with open(QUALITY_PATH, "w", encoding="utf-8") as f:
        json.dump(quality, f, ensure_ascii=False, indent=2)

    print(f"完成：{OUTPUT_PATH}")
    print(f"完成：{QUALITY_PATH}")
    print(f"房源數：{len(df)}")
    print("品質分級：", quality["quality_grade_counts"])

if __name__ == "__main__":
    run()
