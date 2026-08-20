# -*- coding: utf-8 -*-

"""
第42階段：V6.2 效能 Benchmark

用途：
1. 執行既有 v62_stress_test.py
2. 擷取三組壓力測試時間
3. 與 V6.2 Baseline 比較
4. 產生 Markdown Benchmark 報告
5. 不修改 pricing_engine_v6_2.py
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path


# ============================================================
# V6.2 Baseline
# 第41階段正式壓力測試結果
# ============================================================

BASELINE = {
    "100x1000": {
        "listings": 100,
        "transactions": 1000,
        "seconds": 1.78,
    },
    "500x5000": {
        "listings": 500,
        "transactions": 5000,
        "seconds": 44.49,
    },
    "1000x10000": {
        "listings": 1000,
        "transactions": 10000,
        "seconds": 178.17,
    },
}


# ============================================================
# 允許的最大變慢幅度
#
# GitHub Runner 的 CPU / IO 可能有自然波動，
# 因此先設定 50%。
#
# 超過 50%：
# FAIL
#
# 未超過：
# PASS
# ============================================================

MAX_SLOWDOWN = 0.50


# ============================================================
# 執行既有壓力測試
# ============================================================

def run_stress_test():

    script = Path("v62_stress_test.py")

    if not script.exists():
        raise FileNotFoundError(
            "找不到 v62_stress_test.py"
        )

    print("=" * 70)
    print("第42階段：V6.2 Benchmark")
    print("=" * 70)

    print()
    print("執行既有 V6.2 壓力測試...")
    print()

    result = subprocess.run(
        ["python", str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    print(result.stdout)

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(
            "V6.2 壓力測試執行失敗"
        )

    return result.stdout


# ============================================================
# 解析壓力測試結果
# ============================================================

def parse_results(output):

    results = {}

    pattern = re.compile(
        r"V6\.2 壓力測試：\s*"
        r"([\d,]+)\s*在售\s*[×x]\s*([\d,]+)\s*成交"
        r".*?"
        r"執行時間：\s*([\d.]+)\s*秒",
        re.S,
    )

    matches = pattern.findall(output)

    for listings, transactions, seconds in matches:

        listings = int(listings.replace(",", ""))
        transactions = int(
            transactions.replace(",", "")
        )
        seconds = float(seconds)

        key = f"{listings}x{transactions}"

        results[key] = {
            "listings": listings,
            "transactions": transactions,
            "seconds": seconds,
        }

    return results


# ============================================================
# Benchmark 分析
# ============================================================

def analyze(results):

    rows = []

    all_pass = True

    for key, baseline in BASELINE.items():

        current = results.get(key)

        if not current:

            rows.append({
                "key": key,
                "status": "FAIL",
                "message": "找不到測試結果",
            })

            all_pass = False

            continue

        baseline_seconds = baseline["seconds"]
        current_seconds = current["seconds"]

        difference = (
            current_seconds - baseline_seconds
        )

        percentage = (
            difference / baseline_seconds
        ) * 100

        slowdown = (
            difference / baseline_seconds
        )

        if slowdown > MAX_SLOWDOWN:

            status = "FAIL"
            all_pass = False

        else:

            status = "PASS"

        rows.append({
            "key": key,
            "listings": current["listings"],
            "transactions": current["transactions"],
            "baseline": baseline_seconds,
            "current": current_seconds,
            "difference": difference,
            "percentage": percentage,
            "status": status,
        })

    return rows, all_pass


# ============================================================
# 產生 Markdown 報告
# ============================================================

def write_report(rows, all_pass):

    report_dir = Path("reports")
    report_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    report_file = (
        report_dir /
        "v6_2_benchmark_report.md"
    )

    now = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    lines = []

    lines.append(
        "# V6.2 效能 Benchmark 報告"
    )

    lines.append("")
    lines.append(
        f"測試時間：{now}"
    )

    lines.append("")
    lines.append(
        "## Baseline"
    )

    lines.append("")

    lines.append(
        "| 測試規模 | Baseline | 本次 | 差異 | 狀態 |"
    )

    lines.append(
        "|---|---:|---:|---:|---|"
    )

    for row in rows:

        if row["status"] == "FAIL" and "current" not in row:

            lines.append(
                f"| {row['key']} | - | - | - | ❌ FAIL |"
            )

            continue

        percentage = row["percentage"]

        lines.append(
            f"| "
            f"{row['listings']:,} × "
            f"{row['transactions']:,} | "
            f"{row['baseline']:.2f} 秒 | "
            f"{row['current']:.2f} 秒 | "
            f"{percentage:+.1f}% | "
            f"{'✅ PASS' if row['status'] == 'PASS' else '❌ FAIL'} |"
        )

    lines.append("")
    lines.append(
        "## 判定"
    )

    lines.append("")

    if all_pass:

        lines.append(
            "✅ V6.2 Benchmark 通過"
        )

        lines.append(
            ""
        )

        lines.append(
            "所有測試均未超過 Baseline 允許的 50% 變慢門檻。"
        )

    else:

        lines.append(
            "❌ V6.2 Benchmark 未通過"
        )

        lines.append(
            ""
        )

        lines.append(
            "至少一組測試超過允許的效能退化門檻。"
        )

    lines.append("")
    lines.append(
        "## Baseline 原始資料"
    )

    lines.append("")
    lines.append(
        "- 100 × 1,000：1.78 秒"
    )
    lines.append(
        "- 500 × 5,000：44.49 秒"
    )
    lines.append(
        "- 1,000 × 10,000：178.17 秒"
    )

    report_file.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    print()
    print(
        f"Benchmark 報告已產生：{report_file}"
    )


# ============================================================
# 主程式
# ============================================================

def main():

    output = run_stress_test()

    results = parse_results(
        output
    )

    print()
    print("=" * 70)
    print("Benchmark 分析")
    print("=" * 70)

    rows, all_pass = analyze(
        results
    )

    for row in rows:

        if "current" not in row:

            print(
                f"{row['key']} | FAIL | "
                f"{row['message']}"
            )

            continue

        print(
            f"{row['key']} | "
            f"Baseline={row['baseline']:.2f}s | "
            f"Current={row['current']:.2f}s | "
            f"{row['percentage']:+.1f}% | "
            f"{row['status']}"
        )

    write_report(
        rows,
        all_pass
    )

    print()

    if all_pass:

        print(
            "✅ 第42階段 Benchmark 通過"
        )

    else:

        print(
            "❌ 第42階段 Benchmark 未通過"
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()
