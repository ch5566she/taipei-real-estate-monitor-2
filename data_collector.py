# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第三階段：官方實價資料蒐集＋每日歷史資料保存

資料來源：
臺北市政府資料開放平台－臺北市實價個案
"""

import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta


# ============================================================
# 基本設定
# ============================================================

API_URL = (
    "https://data.taipei/api/v1/dataset/"
    "2979c431-7a32-4067-9af2-e716cd825c4b"
    "?scope=resourceAquire"
)

RESOURCE_ID = "2979c431-7a32-4067-9af2-e716cd825c4b"

TARGET_DISTRICTS = {
    "士林區",
    "北投區",
}

PAGE_SIZE = 1000

# 最新資料
OUTPUT_FILE = "data/taipei_transactions.csv"

# 歷史資料
HISTORY_DIR = "history"


# ============================================================
# 取得官方資料
# ============================================================

def fetch_data(offset):
    """從臺北市實價個案 API 取得一批資料。"""

    params = {
        "resource_id": RESOURCE_ID,
        "limit": PAGE_SIZE,
        "offset": offset,
    }

    url = API_URL + "&" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url=url,
        headers={
            "User-Agent": "TaipeiRealEstateMonitor/1.0"
        }
    )

    print(f"正在取得資料：offset={offset}")

    with urllib.request.urlopen(request, timeout=60) as response:
        raw_data = response.read()

    data = json.loads(
        raw_data.decode("utf-8")
    )

    return data.get("result", {}).get("results", [])


# ============================================================
# 保存 CSV
# ============================================================

def save_csv(records, output_file):
    """將資料保存成 CSV。"""

    if not records:
        print("沒有資料可以保存。")
        return

    directory = os.path.dirname(output_file)

    if directory:
        os.makedirs(directory, exist_ok=True)

    # 收集所有欄位
    fieldnames = set()

    for record in records:
        fieldnames.update(record.keys())

    fieldnames = sorted(fieldnames)

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as csvfile:

        writer = csv.DictWriter(
            csvfile,
            fieldnames=fieldnames,
            extrasaction="ignore"
        )

        writer.writeheader()
        writer.writerows(records)

    print("資料儲存完成")
    print(f"檔案：{output_file}")
    print(f"資料筆數：{len(records)}")


# ============================================================
# 保存每日歷史資料
# ============================================================

def save_history(records):
    """
    將每天取得的士林區／北投區資料
    保存到 history/YYYY-MM-DD.csv
    """

    if not records:
        print("沒有資料可以建立歷史紀錄。")
        return

    # 台灣時間 UTC+8
    taiwan_timezone = timezone(timedelta(hours=8))

    today = datetime.now(taiwan_timezone).strftime(
        "%Y-%m-%d"
    )

    os.makedirs(HISTORY_DIR, exist_ok=True)

    history_file = os.path.join(
        HISTORY_DIR,
        f"{today}.csv"
    )

    save_csv(records, history_file)

    print(f"歷史資料已保存：{history_file}")


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 60)
    print("台北市士林區／北投區房市監控系統")
    print("第三階段：官方實價資料蒐集＋歷史資料保存")
    print("=" * 60)

    all_records = []

    offset = 0

    # --------------------------------------------------------
    # 持續取得官方資料
    # --------------------------------------------------------

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

        # 如果不足一頁，代表已經到底
        if len(records) < PAGE_SIZE:
            break

        offset += PAGE_SIZE

    # --------------------------------------------------------
    # 顯示結果
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(
        f"士林區＋北投區總資料："
        f"{len(all_records):,} 筆"
    )
    print("=" * 60)

    if not all_records:
        print("沒有取得士林區／北投區資料。")
        return

    # --------------------------------------------------------
    # 保存最新資料
    # --------------------------------------------------------

    save_csv(
        all_records,
        OUTPUT_FILE
    )

    # --------------------------------------------------------
    # 保存每日歷史資料
    # --------------------------------------------------------

    save_history(
        all_records
    )

    print()
    print("=" * 60)
    print("官方房價資料蒐集完成。")
    print("最新資料與每日歷史資料均已保存。")
    print("=" * 60)


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
