# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第一階段：官方實價資料蒐集

資料來源：
臺北市政府地政局－臺北市實價周報
"""

import csv
import json
import os
import urllib.parse
import urllib.request


# 官方實價周報 API 資源
API_URL = (
    "https://data.taipei/api/v1/dataset/"
    "2979c431-7a32-4067-9af2-e716cd825c4b"
    "?scope=resourceAquire"
)

# 只分析士林區與北投區
TARGET_DISTRICTS = {
    "士林區",
    "北投區",
}

# 每次取得的資料筆數
PAGE_SIZE = 1000

# 輸出檔案
OUTPUT_FILE = "data/taipei_transactions.csv"


def fetch_data(offset):
    """從臺北市實價周報 API 取得一批資料。"""

    params = {
        "resource_id": "2979c431-7a32-4067-9af2-e716cd825c4b",
        "limit": PAGE_SIZE,
        "offset": offset,
    }

    url = API_URL + "&" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TaipeiRealEstateMonitor/1.0"
        },
    )

    print(f"正在取得資料：offset={offset}")

    with urllib.request.urlopen(request, timeout=60) as response:
        raw_data = response.read()

    data = json.loads(
        raw_data.decode("utf-8")
    )

    return data.get("result", {}).get("results", [])


def save_csv(records):
    """將士林區與北投區資料儲存成 CSV。"""

    if not records:
        print("沒有找到士林區或北投區資料。")
        return

    os.makedirs("data", exist_ok=True)

    # 收集所有欄位
    fieldnames = set()

    for record in records:
        fieldnames.update(record.keys())

    fieldnames = sorted(fieldnames)

    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(records)

    print("=" * 60)
    print("資料儲存完成")
    print("=" * 60)
    print(f"檔案：{OUTPUT_FILE}")
    print(f"資料筆數：{len(records):,}")
    print("=" * 60)


def main():
    """主程式。"""

    print("=" * 60)
    print("臺北市士林區／北投區房市監控系統")
    print("第一階段：官方實價資料蒐集")
    print("=" * 60)

    all_records = []
    offset = 0

    while True:

        records = fetch_data(offset)

        if not records:
            break

        for record in records:

            district = str(
                record.get("district", "")
            ).strip()

            if district in TARGET_DISTRICTS:
                all_records.append(record)

        print(
            f"本批取得：{len(records):,} 筆；"
            f"目前目標區域累計：{len(all_records):,} 筆"
        )

        if len(records) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    print()
    print(
        f"士林區＋北投區總資料："
        f"{len(all_records):,} 筆"
    )

    save_csv(all_records)

    print()
    print("官方實價資料蒐集完成。")


if __name__ == "__main__":
    main()
