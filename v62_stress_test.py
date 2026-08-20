# -*- coding: utf-8 -*-

"""
第41階段：V6.2 壓力測試程式

目的：
1. 不修改正式 pricing_engine_v6_2.py
2. 使用合成資料建立不同規模的測試
3. 測試 V6.2 在大量在售物件／成交資料下是否穩定
4. 驗證：
   - 執行時間
   - 成功／失敗筆數
   - 輸出完整性
   - A/B/C 正式估價資格
   - D/E/F 不得進入正式價格計算

預設測試：
100 在售 × 1,000 成交
500 在售 × 5,000 成交
1,000 在售 × 10,000 成交

STRESS_HEAVY=1 時再增加：
2,000 在售 × 20,000 成交
"""

import csv
import os
import sys
import time
import tempfile
from pathlib import Path


# ============================================================
# 找到正式 V6.2 引擎
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

import pricing_engine_v6_2 as engine


# ============================================================
# 測試規模
# ============================================================

TEST_LEVELS = [
    (100, 1000),
    (500, 5000),
    (1000, 10000),
]

if os.environ.get("STRESS_HEAVY", "0") == "1":
    TEST_LEVELS.append((2000, 20000))


# ============================================================
# 建立測試資料
# ============================================================

def create_listing_rows(count):
    rows = []

    for i in range(count):
        rows.append({
            "listing_id": f"STRESS-L-{i+1:06d}",
            "district": "士林區",
            "location": f"士林區中山北路六段{i % 20 + 1}號",
            "title": f"V6.2壓力測試物件{i+1}",
            "total_price": "3000",
            "building_area": "40",
            "unit_price": "75",
            "age": "25",
            "floor": "6",
            "total_floors": "12",
            "rooms": "3",
            "parking": "無",
            "building_type": "華廈",
        })

    return rows


def create_transaction_rows(count):
    rows = []

    for i in range(count):

        # 大部分成交資料設計成可比較樣本
        address_no = i % 20 + 1

        rows.append({
            "transaction_id": f"STRESS-T-{i+1:07d}",
            "district": "士林區",
            "address": f"士林區中山北路六段{address_no}號",
            "building_area": "40",
            "unit_price": str(70 + (i % 11) * 0.5),
            "total_price": str((70 + (i % 11) * 0.5) * 40),
            "transaction_date": "2026-06-01",
            "floor": "6",
            "total_floors": "12",
            "age": "25",
            "building_type": "華廈",
            "parking": "無",
            "case_type": "買賣",
            "case_f": "房屋",
        })

    return rows


def write_csv(path, rows):
    if not rows:
        return

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# 單一壓力測試
# ============================================================

def run_stress_test(listing_count, transaction_count):

    print()
    print("=" * 70)
    print(
        f"V6.2 壓力測試："
        f"{listing_count:,} 在售 × "
        f"{transaction_count:,} 成交"
    )
    print("=" * 70)

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_dir = Path(temp_dir)

        data_dir = temp_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        listing_file = data_dir / "current_listings.csv"
        transaction_file = data_dir / "591_transactions.csv"
        output_file = data_dir / "pricing_decisions.csv"

        listings = create_listing_rows(listing_count)
        transactions = create_transaction_rows(transaction_count)

        write_csv(listing_file, listings)
        write_csv(transaction_file, transactions)

        # ----------------------------------------------------
        # 暫時替換 V6.2 引擎資料路徑
        # 不修改正式程式碼
        # ----------------------------------------------------

        old_listing_file = engine.LISTING_FILE
        old_transaction_files = engine.TRANSACTION_FILES
        old_output_file = engine.OUTPUT_FILE
        old_data_dir = engine.DATA_DIR

        engine.LISTING_FILE = str(listing_file)
        engine.TRANSACTION_FILES = [str(transaction_file)]
        engine.OUTPUT_FILE = str(output_file)
        engine.DATA_DIR = str(data_dir)

        try:

            start_time = time.perf_counter()

            loaded_listings = engine.load_listings()
            loaded_transactions = engine.load_transactions()

            results = []

            success_count = 0
            error_count = 0

            for listing in loaded_listings:

                try:
                    result = engine.decision_for_listing(
                        listing,
                        loaded_transactions
                    )

                    results.append(result)
                    success_count += 1

                except Exception as exc:
                    error_count += 1
                    print(
                        f"ERROR：{listing.get('listing_id')} "
                        f"→ {type(exc).__name__}: {exc}"
                    )

            engine.save_results(results)

            elapsed = time.perf_counter() - start_time

            # ------------------------------------------------
            # 輸出完整性
            # ------------------------------------------------

            output_exists = output_file.exists()

            output_rows = []

            if output_exists:
                with open(
                    output_file,
                    "r",
                    encoding="utf-8-sig",
                    newline=""
                ) as file:

                    output_rows = list(
                        csv.DictReader(file)
                    )

            output_count = len(output_rows)

            complete_output = (
                output_count == listing_count
                and success_count == listing_count
                and error_count == 0
            )

            # ------------------------------------------------
            # V6.2 規則驗證
            # ------------------------------------------------

            formal_count = 0
            insufficient_count = 0
            rule_error_count = 0

            for row in output_rows:

                eligible = row.get(
                    "formal_valuation_eligible",
                    ""
                )

                a = int(float(row.get("grade_a_count", 0) or 0))
                b = int(float(row.get("grade_b_count", 0) or 0))
                c = int(float(row.get("grade_c_count", 0) or 0))
                d = int(float(row.get("grade_d_count", 0) or 0))
                e = int(float(row.get("grade_e_count", 0) or 0))
                f = int(float(row.get("grade_f_count", 0) or 0))

                core = a + b + c

                if eligible == "是":
                    formal_count += 1

                    # 正式估價必須至少有 A/B/C 3 筆
                    if core < 3:
                        rule_error_count += 1

                    # D/E/F 不得進正式價格計算
                    if d > 0 or e > 0 or f > 0:
                        # D/E/F 可以存在於統計結果，
                        # 但不能因此成為正式估價資格。
                        if core < 3:
                            rule_error_count += 1

                else:
                    insufficient_count += 1

            # ------------------------------------------------
            # 結果
            # ------------------------------------------------

            print()
            print(f"輸入在售物件：{listing_count:,}")
            print(f"輸入成交資料：{transaction_count:,}")
            print(f"成功處理：{success_count:,}")
            print(f"失敗：{error_count:,}")
            print(f"輸出筆數：{output_count:,}")
            print(f"正式估價：{formal_count:,}")
            print(f"樣本不足：{insufficient_count:,}")
            print(f"規則錯誤：{rule_error_count:,}")
            print(f"執行時間：{elapsed:.2f} 秒")

            if listing_count > 0:
                print(
                    f"平均每筆："
                    f"{elapsed / listing_count:.6f} 秒"
                )

            print()

            if not output_exists:
                print("❌ FAIL：沒有產生 pricing_decisions.csv")

            elif not complete_output:
                print("❌ FAIL：輸出筆數與輸入不一致")

            elif rule_error_count > 0:
                print("❌ FAIL：V6.2 正式估價規則驗證失敗")

            else:
                print("✅ PASS：本級壓力測試通過")

            return {
                "listing_count": listing_count,
                "transaction_count": transaction_count,
                "elapsed": elapsed,
                "success_count": success_count,
                "error_count": error_count,
                "output_count": output_count,
                "formal_count": formal_count,
                "insufficient_count": insufficient_count,
                "rule_error_count": rule_error_count,
                "passed": (
                    complete_output
                    and rule_error_count == 0
                ),
            }

        finally:

            # ------------------------------------------------
            # 還原正式 V6.2 引擎設定
            # ------------------------------------------------

            engine.LISTING_FILE = old_listing_file
            engine.TRANSACTION_FILES = old_transaction_files
            engine.OUTPUT_FILE = old_output_file
            engine.DATA_DIR = old_data_dir


# ============================================================
# 主程式
# ============================================================

def main():

    print("=" * 70)
    print("第41階段：V6.2 壓力測試框架")
    print("=" * 70)

    print(
        "正式引擎：pricing_engine_v6_2.py"
    )

    print(
        "本測試只建立暫時合成資料，不修改正式 data/ 資料。"
    )

    all_results = []

    for listing_count, transaction_count in TEST_LEVELS:

        result = run_stress_test(
            listing_count,
            transaction_count
        )

        all_results.append(result)

    print()
    print("=" * 70)
    print("V6.2 壓力測試總結")
    print("=" * 70)

    all_passed = True

    for result in all_results:

        status = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print(
            f"{status} | "
            f"{result['listing_count']:,} 在售 × "
            f"{result['transaction_count']:,} 成交 | "
            f"{result['elapsed']:.2f} 秒"
        )

        if not result["passed"]:
            all_passed = False

    print()

    if all_passed:
        print("🎉 第41階段：所有 V6.2 壓力測試通過")
        return 0

    print("❌ 第41階段：至少一級壓力測試失敗")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
