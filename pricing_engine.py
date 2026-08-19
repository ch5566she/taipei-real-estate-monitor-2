# -*- coding: utf-8 -*-
"""
房仲實戰價格決策引擎
第29階段

功能：
1. 讀取 data/current_listings.csv
2. 讀取 data/591_transactions.csv
3. 比對在售物件與歷史成交
4. 計算目前開價與歷史成交價差
5. 計算價格競爭力
6. 產生合理價格區間
7. 產生買方／賣方議價建議
8. 輸出 data/pricing_decisions.csv
"""

from pathlib import Path
import csv
import re
from statistics import median


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

LISTINGS_FILE = DATA_DIR / "current_listings.csv"
TRANSACTIONS_FILE = DATA_DIR / "591_transactions.csv"
OUTPUT_FILE = DATA_DIR / "pricing_decisions.csv"


def to_float(value, default=0.0):
    """安全轉換數字"""
    if value is None:
        return default

    text = str(value).strip()

    if not text:
        return default

    text = text.replace(",", "")
    text = text.replace("萬", "")
    text = text.replace("坪", "")

    try:
        return float(text)
    except ValueError:
        return default


def normalize_address(address):
    """簡化地址，方便比對"""
    if not address:
        return ""

    text = str(address).strip()

    text = text.replace("臺", "台")
    text = text.replace(" ", "")
    text = text.replace("　", "")

    return text


def read_csv(path):
    """讀取 CSV"""
    if not path.exists():
        raise FileNotFoundError(f"找不到資料檔案：{path}")

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_value(row, *names):
    """從多個可能欄位名稱中取得第一個存在的值"""
    for name in names:
        if name in row:
            return row.get(name)
    return ""


def address_match(listing, transaction):
    """判斷在售物件與實價地址是否可能相同"""
    listing_address = normalize_address(
        get_value(listing, "location", "address")
    )

    transaction_address = normalize_address(
        get_value(transaction, "address", "location")
    )

    if not listing_address or not transaction_address:
        return False

    # 完全相同
    if listing_address == transaction_address:
        return True

    # 一方包含另一方
    if listing_address in transaction_address:
        return True

    if transaction_address in listing_address:
        return True

    return False


def get_listing_price(row):
    """取得目前在售總價"""
    return to_float(
        get_value(row, "total_price", "price")
    )


def get_listing_unit_price(row):
    """取得目前在售單價"""
    return to_float(
        get_value(row, "unit_price")
    )


def get_transaction_price(row):
    """取得歷史成交總價"""
    return to_float(
        get_value(row, "total_price", "price")
    )


def get_transaction_unit_price(row):
    """取得歷史成交單價"""
    return to_float(
        get_value(row, "unit_price")
    )


def find_comparables(listing, transactions):
    """
    找尋歷史成交比較案例。

    優先：
    1. 同地址
    2. 同行政區
    3. 建物坪數接近
    """

    matches = []

    listing_district = str(
        get_value(listing, "district")
    ).strip()

    listing_area = to_float(
        get_value(listing, "building_area")
    )

    # 第一層：同地址
    for transaction in transactions:
        if address_match(listing, transaction):
            matches.append(transaction)

    if matches:
        return matches

    # 第二層：同行政區 + 坪數接近
    for transaction in transactions:

        transaction_district = str(
            get_value(transaction, "district")
        ).strip()

        transaction_area = to_float(
            get_value(transaction, "building_area")
        )

        if listing_district and transaction_district:
            if listing_district != transaction_district:
                continue

        if listing_area > 0 and transaction_area > 0:

            area_difference = abs(
                transaction_area - listing_area
            ) / listing_area

            if area_difference <= 0.20:
                matches.append(transaction)

    return matches


def calculate_decision(listing, transactions):
    """產生單一物件價格決策"""

    listing_price = get_listing_price(listing)
    listing_unit_price = get_listing_unit_price(listing)

    listing_area = to_float(
        get_value(listing, "building_area")
    )

    comparables = find_comparables(
        listing,
        transactions
    )

    comparable_units = []

    comparable_prices = []

    for item in comparables:

        unit_price = get_transaction_unit_price(item)
        total_price = get_transaction_price(item)

        if unit_price > 0:
            comparable_units.append(unit_price)

        if total_price > 0:
            comparable_prices.append(total_price)

    if comparable_units:

        median_unit_price = median(
            comparable_units
        )

    else:
        median_unit_price = 0

    if comparable_prices:

        median_transaction_price = median(
            comparable_prices
        )

    else:
        median_transaction_price = 0

    # --------------------------------------------------
    # 開價與歷史成交比較
    # --------------------------------------------------

    if median_unit_price > 0:

        price_gap_percent = (
            listing_unit_price -
            median_unit_price
        ) / median_unit_price * 100

    else:

        price_gap_percent = 0

    # --------------------------------------------------
    # 合理價格區間
    #
    # 採用歷史成交中位單價：
    # - 低標：-5%
    # - 高標：+5%
    #
    # 若沒有成交資料，則不自行估價
    # --------------------------------------------------

    if median_unit_price > 0 and listing_area > 0:

        reasonable_low_unit = (
            median_unit_price * 0.95
        )

        reasonable_high_unit = (
            median_unit_price * 1.05
        )

        reasonable_low_price = (
            reasonable_low_unit *
            listing_area
        )

        reasonable_high_price = (
            reasonable_high_unit *
            listing_area
        )

        # 買方第一口：
        buyer_first_price = (
            reasonable_low_price * 0.95
        )

        # 買方最高建議：
        buyer_max_price = (
            reasonable_high_price * 0.98
        )

        # 賣方合理開價：
        seller_price = (
            reasonable_high_price * 1.05
        )

    else:

        reasonable_low_price = 0
        reasonable_high_price = 0
        buyer_first_price = 0
        buyer_max_price = 0
        seller_price = 0

    # --------------------------------------------------
    # 價格分級
    # --------------------------------------------------

    if median_unit_price <= 0:

        price_grade = "缺乏成交資料"

    elif price_gap_percent <= 5:

        price_grade = "值得追蹤"

    elif price_gap_percent <= 15:

        price_grade = "值得議價"

    else:

        price_grade = "價格過高"

    # --------------------------------------------------
    # 議價空間
    # --------------------------------------------------

    if listing_price > 0 and reasonable_high_price > 0:

        negotiation_percent = (
            listing_price -
            reasonable_high_price
        ) / listing_price * 100

    else:

        negotiation_percent = 0

    return {
        "listing_id":
            get_value(listing, "listing_id"),

        "district":
            get_value(listing, "district"),

        "location":
            get_value(listing, "location", "address"),

        "title":
            get_value(listing, "title"),

        "current_price":
            round(listing_price, 2),

        "current_unit_price":
            round(listing_unit_price, 2),

        "comparable_count":
            len(comparables),

        "median_transaction_price":
            round(median_transaction_price, 2),

        "median_transaction_unit_price":
            round(median_unit_price, 2),

        "price_gap_percent":
            round(price_gap_percent, 2),

        "reasonable_low_price":
            round(reasonable_low_price, 2),

        "reasonable_high_price":
            round(reasonable_high_price, 2),

        "buyer_first_price":
            round(buyer_first_price, 2),

        "buyer_max_price":
            round(buyer_max_price, 2),

        "seller_reasonable_price":
            round(seller_price, 2),

        "negotiation_percent":
            round(negotiation_percent, 2),

        "price_grade":
            price_grade
    }


def save_results(results):
    """輸出分析結果"""

    if not results:
        print("沒有可輸出的價格決策資料。")
        return

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    fieldnames = list(results[0].keys())

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(results)

    print(f"價格決策資料已輸出：{OUTPUT_FILE}")
    print(f"共分析 {len(results)} 筆在售物件")


def main():

    print("=" * 60)
    print("第29階段：房仲實戰價格決策引擎")
    print("=" * 60)

    print()
    print("讀取在售物件……")

    listings = read_csv(
        LISTINGS_FILE
    )

    print(
        f"在售物件：{len(listings)} 筆"
    )

    print()
    print("讀取591實價成交資料……")

    transactions = read_csv(
        TRANSACTIONS_FILE
    )

    print(
        f"歷史成交：{len(transactions)} 筆"
    )

    print()
    print("開始價格決策分析……")

    results = []

    for listing in listings:

        result = calculate_decision(
            listing,
            transactions
        )

        results.append(result)

    save_results(results)

    print()
    print("價格決策分析完成。")


if __name__ == "__main__":
    main()
