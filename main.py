# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
第47-1階段：每日自動化 Pipeline 主控程式

完整流程：

01. 官方實價資料
02. 歷史資料保存
03. 591 在售房源匯入
04. current_listings.csv
05. V6.2
06. V6.3
07. analyzer.py
08. report.py
09. 輸出驗證

重要原則：

1. 不修改 V6.2 核心估價邏輯
2. 不修改 V6.3 分析邏輯
3. 不使用舊房源資料冒充今日資料
4. 不製造假房源
5. 房源資料缺失時，明確標示並停止房源估價鏈
6. 官方實價與市場報告仍可正常產生
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


# ============================================================
# 基本路徑
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = BASE_DIR / "history"
REPORT_DIR = BASE_DIR / "reports"

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


# ============================================================
# 必要輸出
# ============================================================

TRANSACTION_FILE = DATA_DIR / "taipei_transactions.csv"
CURRENT_LISTINGS_FILE = DATA_DIR / "current_listings.csv"

PRICING_FILE = DATA_DIR / "pricing_decisions.csv"

V63_CSV_FILE = DATA_DIR / "comparison_analysis_v6_3.csv"
V63_JSON_FILE = DATA_DIR / "comparison_analysis_v6_3.json"

REPORT_FILE = REPORT_DIR / "latest.html"

# 舊版比價引擎輸出。
# report.py 目前仍會讀取這個檔案。
LEGACY_LISTING_COMPARISON_FILE = (
    DATA_DIR / "listing_comparison.json"
)


# ============================================================
# 顯示
# ============================================================

def header():
    now = datetime.now(TAIPEI_TZ)

    print()
    print("=" * 78)
    print("台北市士林區／北投區房市監控系統")
    print("第47-1階段：每日自動化 Pipeline")
    print("=" * 78)
    print(
        "台灣時間："
        + now.strftime("%Y-%m-%d %H:%M:%S")
    )
    print("=" * 78)


def step(number: int, title: str):
    print()
    print("=" * 78)
    print(
        f"[STEP {number:02d}] {title}"
    )
    print("=" * 78)


# ============================================================
# 執行 Python 模組
# ============================================================

def run_script(
    script_name: str,
    number: int,
    title: str,
) -> bool:

    step(number, title)

    script_path = BASE_DIR / script_name

    if not script_path.exists():
        raise FileNotFoundError(
            f"找不到程式：{script_path}"
        )

    print(
        f"執行：{script_name}"
    )

    start = time.time()

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
        ],
        cwd=str(BASE_DIR),
        check=False,
    )

    elapsed = time.time() - start

    print()
    print(
        f"{script_name} "
        f"執行時間：{elapsed:.2f} 秒"
    )

    if result.returncode != 0:

        raise RuntimeError(
            f"{script_name} 執行失敗 "
            f"(return code={result.returncode})"
        )

    print(
        f"✓ {title} 完成"
    )

    return True


# ============================================================
# CSV 筆數
# ============================================================

def csv_count(path: Path) -> int:

    if not path.exists():
        return 0

    try:

        with path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            rows = list(
                csv.reader(file)
            )

        if len(rows) <= 1:
            return 0

        return len(rows) - 1

    except Exception:

        return 0


# ============================================================
# 檢查檔案
# ============================================================

def file_exists(
    path: Path,
    description: str,
    required: bool = True,
) -> bool:

    if not path.exists():

        if required:

            raise FileNotFoundError(
                f"缺少必要檔案："
                f"{description}\n"
                f"{path}"
            )

        print(
            f"⚠️ {description}不存在："
            f"{path}"
        )

        return False

    if path.stat().st_size == 0:

        if required:

            raise RuntimeError(
                f"檔案為空："
                f"{description}\n"
                f"{path}"
            )

        print(
            f"⚠️ {description}為空："
            f"{path}"
        )

        return False

    print(
        f"✓ {description}"
    )

    return True


# ============================================================
# 清除舊房源分析結果
# ============================================================

def clear_stale_listing_results():

    print()
    print(
        "清除舊的房源分析結果，"
        "避免昨天資料冒充今天。"
    )

    stale_files = [

        PRICING_FILE,

        V63_CSV_FILE,

        V63_JSON_FILE,

        # report.py 目前使用的舊版比價輸出
        LEGACY_LISTING_COMPARISON_FILE,
    ]

    for path in stale_files:

        if path.exists():

            try:

                path.unlink()

                print(
                    f"已移除：{path}"
                )

            except OSError as exc:

                print(
                    f"⚠️ 無法移除："
                    f"{path}"
                )

                print(
                    f"原因：{exc}"
                )


# ============================================================
# Pipeline
# ============================================================

def main():

    pipeline_start = time.time()

    header()

    try:

        # ====================================================
        # STEP 00
        # ====================================================

        step(
            0,
            "建立工作目錄",
        )

        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        HISTORY_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        REPORT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            "✓ data/"
        )

        print(
            "✓ history/"
        )

        print(
            "✓ reports/"
        )


        # ====================================================
        # STEP 01
        # 官方實價＋歷史
        # ====================================================

        run_script(
            "data_collector.py",
            1,
            "官方實價資料蒐集＋歷史保存",
        )

        file_exists(
            TRANSACTION_FILE,
            "官方實價資料",
        )


        # ====================================================
        # STEP 02
        # 591 匯入
        # ====================================================

        run_script(
            "listing_importer.py",
            2,
            "591 在售房源資料匯入",
        )


        # ====================================================
        # STEP 03
        # 建立 current_listings
        # ====================================================

        run_script(
            "listing_collector.py",
            3,
            "建立 current_listings.csv",
        )


        # ====================================================
        # STEP 04
        # 判斷今日是否有真實房源
        # ====================================================

        step(
            4,
            "檢查今日在售房源資料",
        )

        listing_count = csv_count(
            CURRENT_LISTINGS_FILE
        )

        print(
            f"今日士林／北投有效在售房源："
            f"{listing_count:,} 筆"
        )


        # ====================================================
        # 沒有房源
        #
        # 不使用舊資料。
        #
        # 但官方實價市場報告仍繼續。
        # ====================================================

        if listing_count == 0:

            print()
            print(
                "⚠️ 今天沒有有效的真實在售房源。"
            )

            print(
                "⚠️ 不會使用昨天的房源資料。"
            )

            clear_stale_listing_results()

            # =================================================
            # STEP 05
            # V6.2 / V6.3 跳過
            # =================================================

            print()
            print(
                "V6.2：SKIP"
            )

            print(
                "原因：今日沒有 current_listings.csv"
            )

            print(
                "V6.3：SKIP"
            )

            print(
                "原因：沒有 V6.2 輸入資料"
            )


        else:

            # =================================================
            # STEP 05
            # V6.2
            # =================================================

            run_script(
                "pricing_engine_v6_2.py",
                5,
                "V6.2 房仲實戰價格決策",
            )

            file_exists(
                PRICING_FILE,
                "V6.2 pricing_decisions.csv",
            )


            # =================================================
            # STEP 06
            # V6.3
            # =================================================

            run_script(
                "listing_comparator_v6_3.py",
                6,
                "V6.3 智慧比較樣本分析",
            )

            file_exists(
                V63_CSV_FILE,
                "V6.3 CSV",
            )

            file_exists(
                V63_JSON_FILE,
                "V6.3 JSON",
            )


        # ====================================================
        # STEP 07
        # Analyzer
        # ====================================================

        run_script(
            "analyzer.py",
            7,
            "士林／北投市場行情分析",
        )


        # ====================================================
        # STEP 08
        # Report
        # ====================================================

        run_script(
            "report.py",
            8,
            "每日房市專業報告",
        )


        # ====================================================
        # STEP 09
        # 最終驗證
        # ====================================================

        step(
            9,
            "Pipeline 最終驗證",
        )

        file_exists(
            TRANSACTION_FILE,
            "taipei_transactions.csv",
        )

        file_exists(
            REPORT_FILE,
            "reports/latest.html",
        )

        if listing_count > 0:

            file_exists(
                CURRENT_LISTINGS_FILE,
                "current_listings.csv",
            )

            file_exists(
                PRICING_FILE,
                "pricing_decisions.csv",
            )

            file_exists(
                V63_CSV_FILE,
                "comparison_analysis_v6_3.csv",
            )

            file_exists(
                V63_JSON_FILE,
                "comparison_analysis_v6_3.json",
            )

        else:

            print(
                "✓ 今日無房源，"
                "房源估價鏈正確跳過"
            )


        # ====================================================
        # 統計
        # ====================================================

        elapsed = (
            time.time()
            - pipeline_start
        )

        print()
        print("=" * 78)
        print("每日 Pipeline 完成")
        print("=" * 78)

        print(
            f"官方實價："
            f"{csv_count(TRANSACTION_FILE):,} 筆"
        )

        print(
            f"今日在售："
            f"{listing_count:,} 筆"
        )

        print(
            f"V6.2："
            f"{'完成' if listing_count > 0 else '跳過'}"
        )

        print(
            f"V6.3："
            f"{'完成' if listing_count > 0 else '跳過'}"
        )

        print(
            "Analyzer：完成"
        )

        print(
            "Report：完成"
        )

        print(
            f"總執行時間："
            f"{elapsed:.2f} 秒"
        )

        print()
        print(
            "✓ PIPELINE SUCCESS"
        )

        print("=" * 78)

        return 0


    except Exception as exc:

        elapsed = (
            time.time()
            - pipeline_start
        )

        print()
        print("=" * 78)
        print("PIPELINE FAILED")
        print("=" * 78)

        print(
            f"錯誤：{exc}"
        )

        print(
            f"執行時間："
            f"{elapsed:.2f} 秒"
        )

        print()
        print(
            "請查看 GitHub Actions "
            "最後一個 STEP 的 Log。"
        )

        print("=" * 78)

        raise


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
