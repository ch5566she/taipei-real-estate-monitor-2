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
import platform
import shutil
import subprocess
import sys
import time
import traceback
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
# 診斷 / 錯誤輸出強化工具
# ============================================================

CURRENT_STAGE = "尚未開始"


def set_stage(stage_name):
    """記錄目前 Pipeline 階段，發生例外時可直接知道卡在哪一步。"""
    global CURRENT_STAGE
    CURRENT_STAGE = stage_name
    print(f"{CYAN}▶ 目前階段：{stage_name}{RESET}")


def print_runtime_context():
    """輸出 GitHub Actions / 本機執行環境資訊。"""
    print("【執行環境診斷】")
    print(f"Python：{sys.executable}")
    print(f"Python 版本：{sys.version.split()[0]}")
    print(f"作業系統：{platform.platform()}")
    print(f"目前工作目錄：{Path.cwd()}")
    print(f"BASE_DIR：{BASE_DIR}")
    print(f"執行時間：{now_taiwan()}")


def print_file_diagnostic(file_path, label="檔案"):
    """檢查檔案是否存在、大小與最後修改時間。"""
    path = Path(file_path)
    rel = path.relative_to(BASE_DIR) if path.is_absolute() and BASE_DIR in path.parents else path

    if not path.exists():
        print(f"{RED}❌ [{label}] 不存在：{rel}{RESET}")
        return False

    try:
        size = path.stat().st_size
        mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        if size == 0:
            print(f"{YELLOW}⚠️ [{label}] 存在但為 0 bytes：{rel}{RESET}")
            print(f"   最後修改：{mtime}")
            return False

        print(f"{GREEN}✓ [{label}] {rel} | {size:,} bytes | 修改：{mtime}{RESET}")
        return True
    except Exception as exc:
        print(f"{YELLOW}⚠️ [{label}] 無法取得檔案資訊：{rel}{RESET}")
        print(f"   {type(exc).__name__}: {exc}")
        return False


def print_log_tail(text, title, lines=80):
    """將 stdout/stderr 最後 N 行再次整理，方便 GitHub Actions 快速定位。"""
    if not text:
        return

    rows = text.rstrip().splitlines()
    tail = rows[-lines:]

    print()
    print(f"【{title} 最後 {len(tail)} 行】")
    print_separator("-")
    for row in tail:
        safe_print(row)
    print_separator("-")


def print_exception_diagnostic(exc):
    """輸出主程式例外的完整 traceback 與執行環境。"""
    print()
    print_separator("=")
    print(f"{RED}❌ 主程式例外診斷{RESET}")
    print_separator("=")
    print(f"目前階段：{CURRENT_STAGE}")
    print(f"錯誤類型：{type(exc).__name__}")
    print(f"錯誤訊息：{exc}")
    print()
    print("【完整 Python Traceback】")
    print_separator("-")
    safe_print(traceback.format_exc().rstrip())
    print_separator("-")
    print_runtime_context()


def validate_csv_basic(file_path, required_columns=None, min_rows=0, label="CSV"):
    """
    基本 CSV 資料品質檢查：
    - 檔案存在 / 非空
    - 欄位是否存在
    - 資料筆數是否達最低要求
    - 顯示前幾個欄位名稱
    """
    path = Path(file_path)

    if not path.exists():
        print(f"{RED}❌ [{label}] 找不到：{path.relative_to(BASE_DIR)}{RESET}")
        return False

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
            rows = list(reader)

        print(f"【{label} 資料品質】")
        print(f"檔案：{path.relative_to(BASE_DIR)}")
        print(f"欄位數：{len(headers)}")
        print(f"資料筆數：{len(rows)}")
        print(f"欄位：{', '.join(headers[:20])}")

        ok = True

        if required_columns:
            missing = [c for c in required_columns if c not in headers]
            if missing:
                print(f"{RED}❌ 缺少必要欄位：{missing}{RESET}")
                ok = False

        if len(rows) < min_rows:
            print(
                f"{RED}❌ 資料筆數不足：目前 {len(rows)} 筆，"
                f"最低要求 {min_rows} 筆{RESET}"
            )
            ok = False

        if ok:
            print(f"{GREEN}✓ {label} 基本檢查通過{RESET}")
        return ok

    except Exception as exc:
        print(f"{RED}❌ [{label}] 讀取失敗{RESET}")
        print(f"{type(exc).__name__}: {exc}")
        print(f"檔案：{path}")
        return False


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
# STEP 02 前置：房源資料來源 Adapter V54.1
# ============================================================

def run_listing_source_adapter():
    """
    執行房源來源 Adapter，並以「暫存替換」方式讓既有
    listing_importer.py 使用驗證後資料。

    原始 data/incoming_listings.csv 會先備份；
    importer 完成後一定嘗試還原原始檔。
    """
    set_stage("[STEP 02] 房源資料來源 Adapter V54.1")
    print_header("[STEP 02] 房源資料來源 Adapter V54.1")

    source_path = DATA_DIR / "incoming_listings.csv"
    validated_path = DATA_DIR / "incoming_listings_validated.csv"
    backup_path = DATA_DIR / ".incoming_listings_original.csv"

    required_columns = [
        "listing_id",
        "district",
        "total_price",
        "building_area",
        "unit_price",
        "data_quality_grade",
        "can_formal_pricing",
    ]

    if not source_path.exists():
        raise FileNotFoundError(
            f"找不到房源原始資料：{source_path}"
        )

    print_file_diagnostic(source_path, "原始房源資料")

    run_script(
        "listing_source_adapter_v54_1.py",
        "房源資料標準化＋品質驗證；不猜測缺失資料",
    )

    if not validate_csv_basic(
        validated_path,
        required_columns=required_columns,
        min_rows=1,
        label="房源 Adapter 驗證資料",
    ):
        raise RuntimeError(
            "房源 Adapter 輸出驗證失敗，停止後續房源 Pipeline。"
        )

    # 顯示品質摘要
    try:
        import json as _json

        quality_path = DATA_DIR / "listing_source_quality.json"
        if quality_path.exists():
            quality = _json.loads(
                quality_path.read_text(encoding="utf-8")
            )
            print()
            print("【房源 Adapter 品質摘要】")
            print(f"房源總數：{quality.get('total_listings', 0)}")
            print(
                "品質分級："
                f"{quality.get('quality_grade_counts', {})}"
            )
            print(
                "核心資料完整："
                f"{quality.get('core_complete', 0)} 筆"
            )
            print(
                "正式價格候選："
                f"{quality.get('formal_pricing_candidates', 0)} 筆"
            )
    except Exception as exc:
        print(
            f"{YELLOW}⚠️ 無法讀取 Adapter 品質摘要："
            f"{type(exc).__name__}: {exc}{RESET}"
        )

    # 暫存原始檔，讓既有 importer 不需要修改。
    shutil.copy2(source_path, backup_path)

    try:
        shutil.copy2(validated_path, source_path)
        print(
            f"{GREEN}✓ 已將驗證資料暫時提供給 listing_importer.py："
            f"{source_path.relative_to(BASE_DIR)}{RESET}"
        )
        return source_path, backup_path
    except Exception:
        if backup_path.exists():
            shutil.copy2(backup_path, source_path)
        raise


def restore_original_listing_source(source_path, backup_path):
    """還原 Adapter 執行前的原始 incoming_listings.csv。"""
    try:
        if backup_path.exists():
            shutil.copy2(backup_path, source_path)
            backup_path.unlink()
            print(
                f"{GREEN}✓ 已還原原始房源資料："
                f"{source_path.relative_to(BASE_DIR)}{RESET}"
            )
    except Exception as exc:
        print(
            f"{RED}❌ 無法還原原始房源資料："
            f"{type(exc).__name__}: {exc}{RESET}"
        )
        raise


# ============================================================
# 執行外部 Python 腳本
# ============================================================

def run_script(
    script_name: str,
    description: str = "",
):
    """
    執行外部 Python 腳本。

    強化內容：
    1. 完整 stdout / stderr
    2. Return code
    3. 完整 Python traceback（若子程式有輸出）
    4. 最後 80 行錯誤摘要
    5. 執行時間
    6. Python / OS / 工作目錄
    7. 實際 command
    8. 腳本存在、檔案大小檢查
    """
    global CURRENT_STAGE

    CURRENT_STAGE = f"執行 {script_name}"
    script_path = BASE_DIR / script_name

    print()
    print(f"執行：{script_name}")
    if description:
        print(f"說明：{description}")

    if not script_path.exists():
        print_separator("=")
        print(f"{RED}❌ 找不到腳本：{script_path}{RESET}")
        print(f"BASE_DIR：{BASE_DIR}")
        print_separator("=")
        raise FileNotFoundError(f"找不到腳本：{script_path}")

    print()
    print("【執行前診斷】")
    print_runtime_context()
    print(f"腳本：{script_path}")
    print(f"Command：{sys.executable} {script_path}")
    print_file_diagnostic(script_path, "腳本")

    start_time = time.perf_counter()

    try:
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
        print(f"{RED}❌ 無法啟動：{script_name}{RESET}")
        print_separator("=")
        print(f"錯誤類型：{type(exc).__name__}")
        print(f"錯誤訊息：{exc}")
        print(f"執行時間：{elapsed:.2f} 秒")
        print_exception_diagnostic(exc)
        raise

    elapsed = time.perf_counter() - start_time

    if result.stdout:
        print()
        print("【STDOUT】")
        print_separator("-")
        safe_print(result.stdout.rstrip())
        print_separator("-")

    if result.stderr:
        print()
        print("【STDERR / TRACEBACK】")
        print_separator("-")
        safe_print(result.stderr.rstrip())
        print_separator("-")

    if result.returncode == 0:
        print()
        print(f"{GREEN}✓ {script_name} 執行完成{RESET}")
        print(f"{script_name} Return Code：0")
        print(f"{script_name} 執行時間：{elapsed:.2f} 秒")
        return result

    # ---------- 失敗診斷 ----------
    print()
    print_separator("=")
    print(f"{RED}❌ {script_name} 執行失敗{RESET}")
    print_separator("=")

    print("【失敗摘要】")
    print(f"階段：{CURRENT_STAGE}")
    print(f"Script：{script_path}")
    print(f"Return Code：{result.returncode}")
    print(f"Working Directory：{BASE_DIR}")
    print(f"Python：{sys.executable}")
    print(f"Python Version：{sys.version}")
    print(f"Execution Time：{elapsed:.2f} 秒")
    print(f"Command：{sys.executable} {script_path}")

    if result.stdout:
        print_log_tail(result.stdout, "STDOUT", 80)
    else:
        print("【STDOUT】無輸出")

    if result.stderr:
        print_log_tail(result.stderr, "STDERR / TRACEBACK", 100)
    else:
        print(
            f"{YELLOW}⚠️ STDERR 沒有內容。"
            f"請檢查子程式是否以其他方式寫入錯誤。{RESET}"
        )

    print()
    print("【失敗腳本檔案】")
    print_file_diagnostic(script_path, "失敗腳本")

    print()
    print_separator("=")
    print(f"{RED}PIPELINE 中止：{script_name}{RESET}")
    print_separator("=")

    raise RuntimeError(
        f"{script_name} 執行失敗 (return code={result.returncode})"
    )


# ============================================================
# STEP 04
# 檢查今日在售資料
# ============================================================

def check_current_listings():
    """
    檢查 current_listings.csv：
    - 是否存在
    - 是否為空
    - 欄位名稱
    - 資料筆數
    - 缺值概況
    """
    set_stage("[STEP 04] 檢查今日在售房源資料")
    print_header("[STEP 04] 檢查今日在售房源資料")

    file_path = DATA_DIR / "current_listings.csv"

    if not file_path.exists():
        print(f"{YELLOW}⚠️ 找不到：{file_path.relative_to(BASE_DIR)}{RESET}")
        print("⚠️ 這可能代表 STEP 03 沒有成功產生檔案。")
        return 0

    try:
        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)
            headers = reader.fieldnames or []
            rows = list(reader)

        count = len(rows)

        print(f"檔案：{file_path.relative_to(BASE_DIR)}")
        print(f"欄位數：{len(headers)}")
        print(f"資料筆數：{count}")
        print(f"欄位：{', '.join(headers[:25])}")

        if count == 0:
            print(f"{YELLOW}⚠️ current_listings.csv 沒有任何資料列。{RESET}")
            print("請檢查 listing_collector.py 的資料來源與篩選條件。")
            return 0

        # 常見欄位名稱的「存在即檢查」模式，不強迫特定 schema
        candidate_id = next(
            (c for c in ["listing_id", "id", "591_id", "物件編號"] if c in headers),
            None,
        )
        candidate_price = next(
            (c for c in ["price", "總價", "total_price", "售價"] if c in headers),
            None,
        )
        candidate_area = next(
            (c for c in ["area", "坪數", "建物坪數", "building_area"] if c in headers),
            None,
        )

        print()
        print("【資料品質摘要】")

        for label, column in [
            ("物件 ID", candidate_id),
            ("價格", candidate_price),
            ("坪數", candidate_area),
        ]:
            if not column:
                print(f"{YELLOW}⚠️ {label}欄位：找不到可辨識欄位{RESET}")
                continue

            empty_count = sum(
                1 for row in rows
                if not str(row.get(column, "")).strip()
            )
            print(
                f"{label}欄位：{column} | "
                f"空值 {empty_count}/{count}"
            )

        print()
        print(f"{GREEN}✓ 今日士林／北投有效在售房源：{count} 筆{RESET}")
        return count

    except Exception as exc:
        print()
        print(f"{RED}❌ 讀取 current_listings.csv 發生問題{RESET}")
        print(f"錯誤類型：{type(exc).__name__}")
        print(f"錯誤訊息：{exc}")
        print(f"檔案：{file_path}")
        safe_print(traceback.format_exc())
        return 0


# ============================================================
# STEP 09
# Pipeline 最終驗證
# ============================================================

def verify_required_files():
    """
    STEP 09 最終驗證：
    - 必要檔案存在
    - 非 0 bytes
    - latest.html 有基本 HTML 內容
    - 顯示檔案大小
    """
    set_stage("[STEP 09] Pipeline 最終驗證")
    print_header("[STEP 09] Pipeline 最終驗證")

    required_files = [
        DATA_DIR / "taipei_transactions.csv",
        REPORTS_DIR / "latest.html",
        DATA_DIR / "current_listings.csv",
        DATA_DIR / "pricing_decisions.csv",
        DATA_DIR / "comparison_analysis_v6_3.csv",
        DATA_DIR / "comparison_analysis_v6_3.json",
        DATA_DIR / "incoming_listings_validated.csv",
        DATA_DIR / "listing_source_quality.json",
    ]

    all_ok = True

    for file_path in required_files:
        if not print_file_diagnostic(file_path, "必要輸出"):
            all_ok = False

    # HTML 額外驗證
    html_path = REPORTS_DIR / "latest.html"
    if html_path.exists() and html_path.stat().st_size > 0:
        try:
            html_text = html_path.read_text(encoding="utf-8", errors="replace")

            print()
            print("【latest.html 內容驗證】")

            checks = [
                ("HTML 標籤", "<html" in html_text.lower()),
                ("房市報告標題", "房市" in html_text),
                ("第12階段", "第12階段" in html_text),
                ("第14階段", "第14階段" in html_text),
                ("第15階段", "第15階段" in html_text),
                ("第16階段", "第16階段" in html_text),
                ("第17階段", "第17階段" in html_text),
            ]

            for label, ok in checks:
                if ok:
                    print(f"{GREEN}✓ {label}{RESET}")
                else:
                    print(f"{YELLOW}⚠️ 找不到：{label}{RESET}")
                    # 報告內容檢查先列警告，不因文字版面變動直接讓 Pipeline 失敗

        except Exception as exc:
            print(f"{YELLOW}⚠️ latest.html 內容檢查失敗：{exc}{RESET}")

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
        "第54-2階段：Adapter 安全接線＋每日自動化 Pipeline"
    )

    print_separator("=")

    print(
        f"執行時間：{now_taiwan()}"
    )

    print(
        f"BASE_DIR：{BASE_DIR}"
    )

    print()
    print_runtime_context()

    print_separator("=")

    try:

        # ====================================================
        # STEP 00
        # ====================================================

        set_stage("[STEP 00] 建立工作目錄")
        prepare_directories()

        # ====================================================
        # STEP 01
        # ====================================================

        set_stage("[STEP 01] 官方實價資料蒐集＋歷史保存")
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

        source_path, backup_path = run_listing_source_adapter()

        try:
            set_stage("[STEP 02] 591 在售房源資料匯入")
            print_header(
                "[STEP 02] 591 在售房源資料匯入"
            )

            run_script(
                "listing_importer.py",
                "使用 Adapter 驗證後的房源資料進行標準化匯入",
            )

            print(
                f"{GREEN}✓ 591 在售房源資料匯入完成{RESET}"
            )
        finally:
            restore_original_listing_source(
                source_path,
                backup_path,
            )

        # ====================================================
        # STEP 03
        # ====================================================

        set_stage("[STEP 03] 建立 current_listings.csv")
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

        set_stage("[STEP 05] V6.2 房仲實戰價格決策")
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

        set_stage("[STEP 06] V6.3 智慧比較樣本分析")
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

        set_stage("[STEP 07] 士林／北投市場行情分析")
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

        set_stage("[STEP 08] 每日房市專業報告")
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
        print("【最終輸出檔案摘要】")
        for output_file in [
            REPORTS_DIR / "latest.html",
            DATA_DIR / "current_listings.csv",
            DATA_DIR / "pricing_decisions.csv",
            DATA_DIR / "comparison_analysis_v6_3.csv",
            DATA_DIR / "comparison_analysis_v6_3.json",
        ]:
            print_file_diagnostic(output_file, "輸出")

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
        print(f"{RED}PIPELINE FAILED{RESET}")
        print_separator("=")

        print(f"失敗階段：{CURRENT_STAGE}")
        print(f"錯誤類型：{type(exc).__name__}")
        print(f"錯誤訊息：{exc}")
        print(f"Pipeline 執行時間：{pipeline_elapsed:.2f} 秒")

        print_exception_diagnostic(exc)

        print()
        print("【最後診斷建議】")
        print("1. 先找上方最後一個出現 [ERROR] / ❌ 的階段。")
        print("2. 再查看該階段的【STDERR / TRACEBACK】。")
        print("3. 若是資料錯誤，再檢查 data/ 下對應 CSV/JSON。")
        print("4. 若是 report.py 失敗，請直接從 traceback 的檔名＋行號修正。")

        print_separator("=")

        # 保留非 0 exit code，讓 GitHub Actions 正確判斷失敗。
        raise


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
