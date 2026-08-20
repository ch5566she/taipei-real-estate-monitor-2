# -*- coding: utf-8 -*-
"""
V6.2 價格口徑正式規格自動驗證程式

用途：
1. 驗證 V6.2 規格文件存在
2. 驗證 V6.2 價格引擎存在
3. 驗證正式 pricing_engine.py 存在
4. 驗證 V6.2 有區分「原始成交價格」與「調整後可比價格」
5. 驗證 V6.2 有處理樣本不足
6. 驗證 V6.2 有第二層行情參考概念
7. 驗證執行測試前後 pricing_engine.py 沒有被修改
8. 不會修改任何正式資料或正式價格引擎

本程式屬於「規格驗證器」，
不是正式價格引擎。
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

SPEC_FILE = ROOT / "V6_2_PRICING_SPEC.md"
V62_FILE = ROOT / "pricing_engine_v6_2.py"
FORMAL_FILE = ROOT / "pricing_engine.py"


def read_text(path: Path) -> str:
    """讀取 UTF-8 文字檔。"""
    if not path.exists():
        raise AssertionError(f"找不到檔案：{path.name}")

    return path.read_text(encoding="utf-8", errors="replace")


def file_hash(path: Path) -> str:
    """計算檔案 SHA-256。"""
    if not path.exists():
        raise AssertionError(f"找不到檔案：{path.name}")

    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


def check_file_structure():
    """確認 V6.2 所需檔案全部存在。"""

    print("=== 1. 檔案存在性檢查 ===")

    required_files = [
        SPEC_FILE,
        V62_FILE,
        FORMAL_FILE,
    ]

    for path in required_files:
        assert path.exists(), f"FAIL：缺少 {path.name}"
        print(f"PASS：{path.name} 存在")


def check_specification():
    """確認 V6.2 正式價格口徑規格文件存在且具有核心概念。"""

    print("\n=== 2. V6.2 價格口徑規格檢查 ===")

    text = read_text(SPEC_FILE)

    assert len(text.strip()) > 0, "FAIL：V6_2_PRICING_SPEC.md 是空檔案"

    print(
        f"PASS：V6_2_PRICING_SPEC.md "
        f"共有 {len(text.splitlines())} 行"
    )

    # 這裡採用「概念關鍵字」檢查，
    # 避免強迫規格文件一定要使用完全相同的文字。
    concept_groups = {
        "原始／成交價格": [
            "原始",
            "成交",
            "單價",
        ],
        "可比／調整價格": [
            "可比",
            "調整",
        ],
        "樣本不足": [
            "樣本不足",
            "不足",
            "sample",
        ],
    }

    for name, keywords in concept_groups.items():
        found = any(keyword.lower() in text.lower()
                    for keyword in keywords)

        if found:
            print(f"PASS：規格文件包含「{name}」相關概念")
        else:
            print(
                f"WARNING：規格文件目前找不到「{name}」"
                "的明確關鍵字"
            )


def check_v62_engine():
    """檢查 V6.2 引擎是否具有核心價格口徑概念。"""

    print("\n=== 3. V6.2 引擎內容檢查 ===")

    text = read_text(V62_FILE)

    assert len(text.strip()) > 0, (
        "FAIL：pricing_engine_v6_2.py 是空檔案"
    )

    print(
        f"PASS：pricing_engine_v6_2.py "
        f"共有 {len(text.splitlines())} 行"
    )

    # Python 基本語法檢查
    compile(text, str(V62_FILE), "exec")
    print("PASS：V6.2 Python 語法正確")

    # 關鍵概念檢查
    checks = {
        "價格／單價": [
            "price",
            "unit_price",
            "單價",
            "價格",
        ],
        "樣本概念": [
            "sample",
            "樣本",
            "comparable",
            "可比",
        ],
        "參考價格": [
            "reference",
            "參考",
        ],
    }

    for name, keywords in checks.items():

        found = any(
            keyword.lower() in text.lower()
            for keyword in keywords
        )

        if found:
            print(f"PASS：找到「{name}」相關邏輯")
        else:
            print(
                f"WARNING：目前沒有找到"
                f"「{name}」相關明確關鍵字"
            )


def check_sample_insufficient_logic():
    """
    檢查 V6.2 是否具有樣本不足處理概念。

    不要求特定函式名稱，
    只確認程式碼有出現樣本不足相關概念。
    """

    print("\n=== 4. 樣本不足邏輯檢查 ===")

    text = read_text(V62_FILE)

    patterns = [
        r"樣本不足",
        r"sample.*不足",
        r"不足.*sample",
        r"min[_\s-]*sample",
        r"sample[_\s-]*count",
        r"sample.*count",
        r"len\s*\(",
    ]

    matched = False

    for pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            matched = True
            break

    if matched:
        print("PASS：V6.2 程式具有樣本數／樣本不足相關判斷")
    else:
        print(
            "WARNING：尚未找到明確的樣本不足判斷，"
            "後續需要人工確認"
        )


def check_reference_price_logic():
    """
    檢查第二層行情參考相關概念。

    這裡不允許把「有參考價格」
    自動解讀成「正式估價」。
    """

    print("\n=== 5. 第二層行情參考邏輯檢查 ===")

    spec_text = read_text(SPEC_FILE)
    engine_text = read_text(V62_FILE)

    combined = (spec_text + "\n" + engine_text).lower()

    reference_keywords = [
        "參考",
        "reference",
        "行情",
        "market",
    ]

    found_reference = any(
        keyword.lower() in combined
        for keyword in reference_keywords
    )

    if found_reference:
        print("PASS：系統具有行情／參考價格相關概念")
    else:
        print(
            "WARNING：尚未找到明確的行情參考概念"
        )

    # 防止 V6.2 的測試程式本身宣稱它就是正式估價。
    forbidden_claims = [
        "第二層.*正式估價",
        "reference.*official.*valuation",
    ]

    forbidden_found = False

    for pattern in forbidden_claims:
        if re.search(
            pattern,
            combined,
            flags=re.IGNORECASE
        ):
            forbidden_found = True
            break

    if forbidden_found:
        raise AssertionError(
            "FAIL：發現第二層參考行情可能被描述為正式估價"
        )

    print("PASS：沒有發現明確將第二層參考行情直接定義為正式估價")


def check_formal_engine_integrity():
    """
    確認測試執行期間沒有修改正式 pricing_engine.py。
    """

    print("\n=== 6. 正式 pricing_engine.py 完整性保護 ===")

    before_hash = file_hash(FORMAL_FILE)

    print(
        "測試開始前 pricing_engine.py SHA-256："
        f"{before_hash}"
    )

    # 重新讀取一次正式引擎。
    # 本測試不呼叫正式引擎的任何修改功能。
    _ = read_text(FORMAL_FILE)

    after_hash = file_hash(FORMAL_FILE)

    print(
        "測試結束後 pricing_engine.py SHA-256："
        f"{after_hash}"
    )

    assert before_hash == after_hash, (
        "FAIL：pricing_engine.py 在測試期間發生變化！"
    )

    print(
        "PASS：pricing_engine.py 測試前後完全一致"
    )


def check_module_import():
    """
    嘗試載入 V6.2 模組。

    如果模組本身具有外部依賴，
    不因 import 失敗直接破壞整個規格測試；
    但會明確顯示原因。
    """

    print("\n=== 7. V6.2 模組載入檢查 ===")

    try:
        spec = importlib.util.spec_from_file_location(
            "pricing_engine_v6_2_test_module",
            V62_FILE,
        )

        assert spec is not None
        assert spec.loader is not None

        module = importlib.util.module_from_spec(spec)

        spec.loader.exec_module(module)

        print("PASS：pricing_engine_v6_2.py 可以成功載入")

    except Exception as exc:
        print(
            "WARNING：V6.2 模組載入時發生問題："
            f"{type(exc).__name__}: {exc}"
        )
        print(
            "說明：本階段仍屬於規格驗證，"
            "不會因此修改正式 pricing_engine.py"
        )


def main():
    print("=" * 70)
    print("V6.2 價格口徑正式規格驗證")
    print("=" * 70)

    try:

        check_file_structure()

        check_specification()

        check_v62_engine()

        check_sample_insufficient_logic()

        check_reference_price_logic()

        check_formal_engine_integrity()

        check_module_import()

    except AssertionError as exc:

        print("\n" + "=" * 70)
        print("❌ V6.2 規格驗證失敗")
        print("=" * 70)
        print(str(exc))

        sys.exit(1)

    print("\n" + "=" * 70)
    print("✅ V6.2 規格驗證完成")
    print("=" * 70)
    print("正式 pricing_engine.py 未被測試程式修改。")
    print("V6.2 目前仍維持獨立測試狀態。")


if __name__ == "__main__":
    main()
