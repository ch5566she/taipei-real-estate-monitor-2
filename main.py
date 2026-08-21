# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
每日自動化 Pipeline 主程式

功能：
STEP 00 建立工作目錄
STEP 01 官方實價資料蒐集＋歷史保存
STEP 02 591 在售房源資料匯入
STEP 03 建立 current_listings.csv
STEP 04 檢查今日在售房源資料
STEP 05 V6.2 房仲實戰價格決策
STEP 06 V6.3 智慧比較樣本分析
STEP 07 士林／北投市場行情分析
STEP 08 每日房市專業報告
STEP 09 Pipeline 最終驗證

本版本特別強化：
1. subprocess 完整 stdout / stderr 收集
2. Python Traceback 完整輸出
3. 顯示失敗腳本
4. 顯示 return code
5. 顯示執行時間
6. 顯示目前工作目錄
7. 顯示 Python 執行檔
8. 顯示環境資訊
9. report.py 發生錯誤時，不再只顯示「return code=1」
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ============================================================
# 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = BASE_DIR / "history"
REPORTS_DIR = BASE_DIR / "reports"


# ============================================================
# 顏色 / GitHub Actions 顯示
# ============================================================

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"


# ============================================================
# 基本工具
# ============================================================

def now_taiwan():
    """
    顯示目前時間。

    GitHub Actions 通常以 UTC 執行，
    這裡單純使用系統時間避免額外依賴。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_separator(char="=", length=78):
    print(char * length)


def print_header(title):
    print()
    print_separator("=")
    print(title)
    print_separator("=")


def safe_print(text):
    """
    避免 GitHub Actions 遇到特殊編碼導致輸出問題。
    """
    if text is None:
        return

    try:
        print(text)
    except UnicodeEncodeError:
        print(
            text.encode("utf-8", errors="replace")
            .decode("utf-8", errors="replace")
        )


# ============================================================
# 建立工作目錄
# ============================================================

def prepare_directories():
    print_header("[STEP 00] 建立工作目錄")

    directories = [
        DATA_DIR,
        HISTORY_DIR,
        REPORTS_DIR,
    ]

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        print(f"✓ {directory.relative_to(BASE_DIR)}/")


# ============================================================
# 執行外部 Python 腳本
# ============================================================

def run_script(
    script_name: str,
    description: str = "",
):
    """
    執行 Python 腳本。

    這裡是本次最重要的錯誤強化區。

    如果子程式失敗：

        stdout
        stderr
        traceback
        return code
        執行時間
        Python 路徑
        工作目錄

    全部會印出來。
    """

    script_path = BASE_DIR / script_name

    print()
    print(f"執行：{script_name}")

    if description:
        print(f"說明：{description}")

    # --------------------------------------------------------
    # 腳本存在檢查
    # --------------------------------------------------------

    if not script_path.exists():
        print()
        print_separator("=")
        print(
            f"{RED}❌ 找不到腳本：{script_path}{RESET}"
        )
        print_separator("=")

        raise FileNotFoundError(
            f"找不到腳本：{script_path}"
        )

    # --------------------------------------------------------
    # 執行前資訊
    # --------------------------------------------------------

    print()
    print("【執行環境】")
    print(f"Python：{sys.executable}")
    print(f"Python 版本：{sys.version.split()[0]}")
    print(f"工作目錄：{BASE_DIR}")
    print(f"腳本：{script_path}")

    start_time = time.perf_counter()

    try:

        # ----------------------------------------------------
        # 非常重要：
        #
        # capture_output=True
        # 讓 stdout / stderr 都被抓回來。
        #
        # text=True
        # 讓結果直接以文字處理。
        #
        # encoding=utf-8
        # 確保中文輸出正常。
        #
        # errors=replace
        # 即使遇到奇怪字元，也不要讓 main.py 自己掛掉。
        # ----------------------------------------------------

        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
            ],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    except Exception as exc:

        elapsed = time.perf_counter() - start_time

        print()
        print_separator("=")
        print(
            f"{RED}❌ 無法啟動：{script_name}{RESET}"
        )
        print_separator("=")

        print()
        print("【Python Exception】")
        print(type(exc).__name__)
        print(str(exc))

        print()
        print("【執行時間】")
        print(f"{elapsed:.2f} 秒")

        print()
        print("【工作目錄】")
        print(BASE_DIR)

        print()
        print("【Python】")
        print(sys.executable)

        print_separator("=")

        raise

    elapsed = time.perf_counter() - start_time

    # --------------------------------------------------------
    # 正常輸出
    # --------------------------------------------------------

    if result.stdout:
        print()
        print("【STDOUT】")
        print_separator("-")
        safe_print(result.stdout.rstrip())
        print_separator("-")

    # --------------------------------------------------------
    # 錯誤輸出
    # --------------------------------------------------------

    if result.stderr:
        print()
        print("【STDERR / TRACEBACK】")
        print_separator("-")
        safe_print(result.stderr.rstrip())
        print_separator("-")

    # --------------------------------------------------------
    # 成功
    # --------------------------------------------------------

    if result.returncode == 0:

        print()
        print(
            f"{GREEN}✓ {script_name} 執行完成{RESET}"
        )

        print(
            f"{script_name} 執行時間："
            f"{elapsed:.2f} 秒"
        )

        return result

    # --------------------------------------------------------
    # 失敗
    # --------------------------------------------------------

    print()
    print_separator("=")
    print(
        f"{RED}❌ {script_name} 執行失敗{RESET}"
    )
    print_separator("=")

    print()
    print("【Return Code】")
    print(result.returncode)

    print()
    print("【Script】")
    print(script_path)

    print()
    print("【Working Directory】")
    print(BASE_DIR)

    print()
    print("【Python】")
    print(sys.executable)

    print()
    print("【Python Version】")
    print(sys.version)

    print()
    print("【Execution Time】")
    print(f"{elapsed:.2f} 秒")

    # --------------------------------------------------------
    # 如果 stdout / stderr 已經在上面顯示過，
    # 這裡再特別提醒使用者。
    # --------------------------------------------------------

    if result.stdout:
        print()
        print("【完整 STDOUT 已於上方顯示】")

    if result.stderr:
        print()
        print("【完整 STDERR / Traceback 已於上方顯示】")
    else:
        print()
        print(
            "⚠️ STDERR 沒有內容。"
            "可能是子程式使用其他方式輸出錯誤。"
        )

    print()
    print_separator("=")
    print(
        f"{RED}PIPELINE 中止：{script_name}{RESET}"
    )
    print_separator("=")

    raise RuntimeError(
        f"{script_name} 執行失敗 "
        f"(return code={result.returncode})"
    )


# ============================================================
# STEP 04
# 檢查今日在售資料
# ============================================================

def check_current_listings():
    """
    檢查 current_listings.csv 是否存在，
    並顯示目前資料筆數。

    注意：
    這裡只做檢查，不重新處理資料。
    """

    print_header("[STEP 04] 檢查今日在售房源資料")

    file_path = DATA_DIR / "current_listings.csv"

    if not file_path.exists():

        print(
            f"{YELLOW}⚠️ 找不到："
            f"{file_path.relative_to(BASE_DIR)}{RESET}"
        )

        return 0

    try:

        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            rows = list(reader)

        count = len(rows)

        print(
            f"今日士林／北投有效在售房源："
            f"{count} 筆"
        )

        return count

    except Exception as exc:

        print()
        print(
            f"{YELLOW}⚠️ 讀取 current_listings.csv 發生問題{RESET}"
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        # 這裡不直接讓 Pipeline 掛掉，
        # 因為真正資料處理是在 listing_collector.py。
        return 0


# ============================================================
# STEP 09
# Pipeline 最終驗證
# ============================================================

def verify_required_files():
    """
    最終確認重要輸出檔案是否存在。
    """

    print_header("[STEP 09] Pipeline 最終驗證")

    required_files = [
        DATA_DIR / "taipei_transactions.csv",
        REPORTS_DIR / "latest.html",
        DATA_DIR / "current_listings.csv",
        DATA_DIR / "pricing_decisions.csv",
        DATA_DIR / "comparison_analysis_v6_3.csv",
        DATA_DIR / "comparison_analysis_v6_3.json",
    ]

    all_ok = True

    for file_path in required_files:

        if file_path.exists():

            print(
                f"{GREEN}✓ "
                f"{file_path.relative_to(BASE_DIR)}"
                f"{RESET}"
            )

        else:

            print(
                f"{RED}❌ "
                f"{file_path.relative_to(BASE_DIR)}"
                f"{RESET}"
            )

            all_ok = False

    return all_ok


# ============================================================
# 取得資料筆數
# ============================================================

def count_csv_rows(file_path):
    """
    簡單計算 CSV 資料筆數。
    """

    if not file_path.exists():
        return 0

    try:

        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.reader(file)

            rows = list(reader)

        if len(rows) <= 1:
            return 0

        return len(rows) - 1

    except Exception:
        return 0


# ============================================================
# Pipeline 主流程
# ============================================================

def main():

    pipeline_start = time.perf_counter()

    print()
    print_separator("=")

    print(
        "台北市士林區／北投區房市監控系統"
    )

    print(
        "第47-1階段：每日自動化 Pipeline"
    )

    print_separator("=")

    print(
        f"執行時間：{now_taiwan()}"
    )

    print(
        f"BASE_DIR：{BASE_DIR}"
    )

    print_separator("=")

    try:

        # ====================================================
        # STEP 00
        # ====================================================

        prepare_directories()

        # ====================================================
        # STEP 01
        # ====================================================

        print_header(
            "[STEP 01] 官方實價資料蒐集＋歷史保存"
        )

        run_script(
            "data_collector.py",
            "官方實價資料蒐集＋歷史資料保存",
        )

        print(
            f"{GREEN}✓ 官方實價資料蒐集＋歷史保存完成{RESET}"
        )

        # ====================================================
        # STEP 02
        # ====================================================

        print_header(
            "[STEP 02] 591 在售房源資料匯入"
        )

        run_script(
            "listing_importer.py",
            "591 在售房源資料匯入",
        )

        print(
            f"{GREEN}✓ 591 在售房源資料匯入完成{RESET}"
        )

        # ====================================================
        # STEP 03
        # ====================================================

        print_header(
            "[STEP 03] 建立 current_listings.csv"
        )

        run_script(
            "listing_collector.py",
            "建立今日有效在售房源資料",
        )

        print(
            f"{GREEN}✓ 建立 current_listings.csv 完成{RESET}"
        )

        # ====================================================
        # STEP 04
        # ====================================================

        current_count = check_current_listings()

        # ====================================================
        # STEP 05
        # ====================================================

        print_header(
            "[STEP 05] V6.2 房仲實戰價格決策"
        )

        run_script(
            "pricing_engine_v6_2.py",
            "V6.2 可比樣本品質分級＋價格決策",
        )

        print(
            f"{GREEN}✓ V6.2 房仲實戰價格決策完成{RESET}"
        )

        # ====================================================
        # STEP 06
        # ====================================================

        print_header(
            "[STEP 06] V6.3 智慧比較樣本分析"
        )

        run_script(
            "listing_comparator_v6_3.py",
            "V6.3 智慧比較樣本分析",
        )

        print(
            f"{GREEN}✓ V6.3 智慧比較樣本分析完成{RESET}"
        )

        # ====================================================
        # STEP 07
        # ====================================================

        print_header(
            "[STEP 07] 士林／北投市場行情分析"
        )

        run_script(
            "analyzer.py",
            "士林／北投市場行情分析",
        )

        print(
            f"{GREEN}✓ 士林／北投市場行情分析完成{RESET}"
        )

        # ====================================================
        # STEP 08
        # ====================================================

        print_header(
            "[STEP 08] 每日房市專業報告"
        )

        run_script(
            "report.py",
            "每日房市專業報告",
        )

        print(
            f"{GREEN}✓ 每日房市專業報告完成{RESET}"
        )

        # ====================================================
        # STEP 09
        # ====================================================

        verification_ok = verify_required_files()

        if not verification_ok:

            print()
            print_separator("=")

            print(
                f"{RED}❌ Pipeline 最終驗證失敗{RESET}"
            )

            print_separator("=")

            raise RuntimeError(
                "Pipeline 最終驗證失敗："
                "缺少必要輸出檔案"
            )

        # ====================================================
        # Pipeline Success
        # ====================================================

        pipeline_elapsed = (
            time.perf_counter()
            - pipeline_start
        )

        transactions_count = count_csv_rows(
            DATA_DIR / "taipei_transactions.csv"
        )

        print()
        print_separator("=")

        print(
            "每日 Pipeline 完成"
        )

        print_separator("=")

        print(
            f"官方實價：{transactions_count} 筆"
        )

        print(
            f"今日在售：{current_count} 筆"
        )

        print(
            "V6.2：完成"
        )

        print(
            "V6.3：完成"
        )

        print(
            "Analyzer：完成"
        )

        print(
            "Report：完成"
        )

        print(
            f"總執行時間："
            f"{pipeline_elapsed:.2f} 秒"
        )

        print()

        print(
            f"{GREEN}✓ PIPELINE SUCCESS{RESET}"
        )

        print_separator("=")

    except Exception as exc:

        pipeline_elapsed = (
            time.perf_counter()
            - pipeline_start
        )

        print()
        print_separator("=")

        print(
            f"{RED}PIPELINE FAILED{RESET}"
        )

        print_separator("=")

        print()
        print("【錯誤類型】")
        print(type(exc).__name__)

        print()
        print("【錯誤訊息】")
        print(str(exc))

        print()
        print("【Pipeline 執行時間】")
        print(f"{pipeline_elapsed:.2f} 秒")

        print()
        print("【目前工作目錄】")
        print(BASE_DIR)

        print()
        print("【Python】")
        print(sys.executable)

        print()
        print("【Python 版本】")
        print(sys.version)

        print()
        print(
            "⚠️ 請查看上方最後一個失敗腳本的 "
            "【STDERR / TRACEBACK】區塊。"
        )

        print_separator("=")

        # 保留非 0 exit code，
        # 讓 GitHub Actions 正確判斷失敗。
        raise


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
