# -*- coding: utf-8 -*-
"""
台北市士林區／北投區
第26階段：在售物件 × 實價成交多層級比價＋房仲實戰定價引擎
（A同門牌／同棟 → B同路段高度可比 → C同生活圈 → D區域行情 → E排除）

功能：
1. 讀取 data/current_listings.csv
2. 讀取 data/taipei_transactions.csv
3. 只使用住宅買賣成交資料
4. 排除純土地、租賃等非住宅成交
5. 同行政區＋同路段優先比價
6. 建物坪數 ±25% 優先匹配
7. 建物類型相近時提高權重
8. 計算成交平均／中位數／Q1／Q3
9. 計算目前在售物件開價相對市場的溢價／折價
10. 產生買方議價建議
11. 產生賣方定價建議
12. 產生市場判斷等級
13. 車位拆價與房屋本體單價校正
14. 屋齡／樓層／坪數／成交時間校正
15. 以樣本權重計算市場合理單價
16. 產生房仲實戰五段價格：目前開價／市場合理價／合理成交區間／買方建議出價／賣方建議底價
17. 將結果輸出至 data/listing_comparison.json

注意：
本程式先獨立運作，不修改既有 analyzer.py / report.py / main.py。
"""

import csv
import json
import math
import os
import re
from datetime import datetime
from statistics import mean, median


# ============================================================
# 路徑設定
# ============================================================

def find_file(filename):
    """
    在 GitHub Actions runner 的常見工作目錄中尋找檔案。

    原因：
    workflow 目前不是標準 checkout 後直接執行，而是可能把程式下載到
    巢狀目錄、再由前一個步驟產生 CSV。此時 __file__/data 不一定就是
    CSV 實際所在位置。
    """
    start = os.path.abspath(os.path.dirname(__file__))

    # 第一優先：程式所在目錄往上找 data/filename
    current = start
    for _ in range(8):
        direct = os.path.join(current, "data", filename)
        if os.path.isfile(direct):
            return os.path.abspath(direct)

        direct2 = os.path.join(current, filename)
        if os.path.isfile(direct2):
            return os.path.abspath(direct2)

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # 第二優先：目前工作目錄往上找
    current = os.path.abspath(os.getcwd())
    for _ in range(8):
        direct = os.path.join(current, "data", filename)
        if os.path.isfile(direct):
            return os.path.abspath(direct)

        direct2 = os.path.join(current, filename)
        if os.path.isfile(direct2):
            return os.path.abspath(direct2)

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # 第三優先：GitHub Actions workspace 內遞迴搜尋。
    # 只搜尋 /home/runner/work，避免掃描整個系統。
    workspace = "/home/runner/work"
    if os.path.isdir(workspace):
        matches = []
        for root, dirs, files in os.walk(workspace):
            # 排除不必要的大型目錄
            dirs[:] = [
                d for d in dirs
                if d not in {".git", "__pycache__", ".venv", "node_modules"}
            ]

            if filename in files:
                matches.append(os.path.join(root, filename))

        if matches:
            # 優先選擇包含 data 目錄的結果
            data_matches = [
                p for p in matches
                if os.path.basename(os.path.dirname(p)) == "data"
            ]
            return os.path.abspath(sorted(data_matches or matches)[0])

    return None


def find_repo_root():
    listing_path = find_file("current_listings.csv")

    if listing_path:
        return os.path.dirname(os.path.dirname(listing_path))

    return os.path.abspath(os.path.dirname(__file__))


BASE_DIR = find_repo_root()

_LISTING_FOUND = find_file("current_listings.csv")
_TRANSACTION_FOUND = find_file("taipei_transactions.csv")

LISTING_FILE = (
    _LISTING_FOUND
    if _LISTING_FOUND
    else os.path.join(BASE_DIR, "data", "current_listings.csv")
)

TRANSACTION_FILE = (
    _TRANSACTION_FOUND
    if _TRANSACTION_FOUND
    else os.path.join(BASE_DIR, "data", "taipei_transactions.csv")
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "data",
    "listing_comparison.json"
)


# ============================================================
# 基本工具
# ============================================================

def to_float(value):
    """安全轉換數字。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = text.replace(",", "")
    text = text.replace("萬", "")
    text = text.replace("元", "")

    try:
        number = float(text)

        if math.isnan(number):
            return None

        return number

    except Exception:
        return None


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


def normalize_location(value):
    """
    統一路段名稱格式。

    例如：
    臺北市士林區中山北路五段
    → 中山北路五段
    """

    text = clean_text(value)

    if not text:
        return ""

    prefixes = [
        "臺北市士林區",
        "臺北市北投區",
        "台北市士林區",
        "台北市北投區",
        "臺北市",
        "台北市",
    ]

    for prefix in prefixes:
        text = text.replace(prefix, "")

    text = text.replace("臺北市", "")
    text = text.replace("台北市", "")

    return text.strip()


def extract_street(location):
    """
    從地址／位置文字抓出主要道路。

    例如：
    中山北路五段123號
    → 中山北路五段

    北科路
    → 北科路
    """

    text = normalize_location(location)

    if not text:
        return ""

    # 優先抓「路／街」及其後的段
    patterns = [
        r"(.+?路[一二三四五六七八九十0-9]*段)",
        r"(.+?街[一二三四五六七八九十0-9]*段)",
        r"(.+?大道[一二三四五六七八九十0-9]*段)",
        r"(.+?路)",
        r"(.+?街)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return match.group(1).strip()

    return text


def normalize_building_type(value):
    """
    將實價登錄建物類型簡化成：
    公寓 / 華廈 / 大樓 / 其他
    """

    text = clean_text(value)

    if not text:
        return "未知"

    if "公寓" in text:
        return "公寓"

    if "華廈" in text:
        return "華廈"

    if "大樓" in text:
        return "大樓"

    if "透天" in text:
        return "透天"

    return "其他"


def roc_date_to_iso(value):
    """
    實價資料 sdate 通常為民國年月日，例如：
    1150715 → 2026-07-15
    """

    text = clean_text(value)

    if not text:
        return ""

    # 已經是西元日期
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", text):
        try:
            return datetime.strptime(
                text,
                "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
        except Exception:
            return ""

    digits = re.sub(r"\D", "", text)

    if len(digits) != 7:
        return ""

    try:
        year = int(digits[:3]) + 1911
        month = int(digits[3:5])
        day = int(digits[5:7])

        return datetime(
            year,
            month,
            day
        ).strftime("%Y-%m-%d")

    except Exception:
        return ""


def percentile(values, p):
    """
    簡單百分位數計算。
    """

    if not values:
        return None

    values = sorted(values)

    if len(values) == 1:
        return values[0]

    index = (len(values) - 1) * p

    lower = math.floor(index)
    upper = math.ceil(index)

    if lower == upper:
        return values[lower]

    weight = index - lower

    return (
        values[lower] * (1 - weight)
        + values[upper] * weight
    )


def round_number(value, digits=2):
    if value is None:
        return None

    return round(float(value), digits)


# ============================================================
# 讀取在售物件
# ============================================================

def load_listings():
    global LISTING_FILE

    if not os.path.exists(LISTING_FILE):
        fresh_path = find_file("current_listings.csv")
        if fresh_path:
            LISTING_FILE = fresh_path

    if not os.path.exists(LISTING_FILE):
        raise FileNotFoundError(
            "找不到在售物件資料。"
            f"\n目前工作目錄：{os.getcwd()}"
            f"\n程式位置：{os.path.abspath(__file__)}"
            f"\n最後搜尋路徑：{LISTING_FILE}"
            "\n請確認「執行在售案源整理」步驟是否真的產生 current_listings.csv。"
        )

    listings = []

    with open(
        LISTING_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            status = clean_text(
                row.get("status")
            ).lower()

            # 只分析 active
            if status and status not in {
                "active",
                "在售",
                "有效"
            }:
                continue

            district = clean_text(
                row.get("district")
            )

            if district not in {
                "士林區",
                "北投區"
            }:
                continue

            area = to_float(
                row.get("building_area")
            )

            unit_price = to_float(
                row.get("unit_price")
            )

            if area is None or area <= 0:
                continue

            if unit_price is None or unit_price <= 0:
                continue

            location = clean_text(
                row.get("location")
            )

            listing = {
                "listing_id": clean_text(
                    row.get("listing_id")
                ),
                "district": district,
                "location": location,
                "street": extract_street(location),
                "title": clean_text(
                    row.get("title")
                ),
                "total_price": to_float(
                    row.get("total_price")
                ),
                "building_area": area,
                "unit_price": unit_price,
                "building_type": normalize_building_type(
                    row.get("building_type") or row.get("buitype")
                ),
                "building_name": clean_text(
                    row.get("building_name") or row.get("community_name") or row.get("project_name")
                ),
                "age": to_float(
                    row.get("age")
                ),
                "floor": to_float(
                    row.get("floor")
                ),
                "total_floors": to_float(
                    row.get("total_floors")
                ),
                "rooms": to_float(
                    row.get("rooms")
                ),
                "halls": to_float(
                    row.get("halls")
                ),
                "bathrooms": to_float(
                    row.get("bathrooms")
                ),
                "parking": clean_text(
                    row.get("parking")
                ),
                "parking_price": to_float(
                    row.get("parking_price") or row.get("pprice")
                ),
                "parking_area": to_float(
                    row.get("parking_area") or row.get("parea") or row.get("parking_area_ping")
                ),
                "address_key": address_key(location),
                "unit_key": exact_unit_key(
                    location,
                    row.get("floor")
                ),
                "source": clean_text(
                    row.get("source")
                ),
                "url": clean_text(
                    row.get("url")
                ),
                "updated_at": clean_text(
                    row.get("updated_at")
                ),
            }

            listings.append(listing)

    return listings


# ============================================================
# 讀取實價成交
# ============================================================

def load_transactions():
    if not os.path.exists(TRANSACTION_FILE):
        raise FileNotFoundError(
            f"找不到實價成交資料：{TRANSACTION_FILE}"
        )

    transactions = []

    with open(
        TRANSACTION_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            # 只使用買賣
            case_t = clean_text(
                row.get("case_t")
            )

            if case_t != "買賣":
                continue

            district = clean_text(
                row.get("district")
            )

            if district not in {
                "士林區",
                "北投區"
            }:
                continue

            # 純土地排除
            case_f = clean_text(
                row.get("case_f")
            )

            if case_f == "土地":
                continue

            area = to_float(
                row.get("farea")
            )

            unit_price = to_float(
                row.get("uprice")
            )

            if area is None or area <= 0:
                continue

            if unit_price is None or unit_price <= 0:
                continue

            building_type = normalize_building_type(
                row.get("buitype")
            )

            # 排除明顯不是住宅的類型
            if building_type == "其他":

                # 如果沒有建物類型，但明確有房地資料，
                # 保留作為 fallback 成交資料
                if "房地" not in case_f:
                    continue

            location = clean_text(
                row.get("location")
            )

            transaction = {
                "id": row.get("_id"),
                "source": "MOI",
                "district": district,
                "location": location,
                "street": extract_street(location),
                "building_type": building_type,
                "area": area,
                "unit_price": unit_price,
                "transaction_price": to_float(
                    row.get("tprice")
                ),
                "date": roc_date_to_iso(
                    row.get("sdate")
                ),
                "age": to_float(
                    row.get("age") or row.get("building_age")
                ),
                "floor": row.get("build_l"),
                "total_floors": row.get("sbuild"),
                "rooms": row.get("build_r"),
                "parking_price": to_float(
                    row.get("pprice")
                ),
                "parking_area": to_float(
                    row.get("parea") or row.get("parking_area")
                ),
                "address_key": address_key(location),
                "unit_key": exact_unit_key(
                    location,
                    row.get("build_l")
                ),
                "case_f": case_f,
                "building_name": clean_text(
                    row.get("build_name")
                ),
                "remark": clean_text(
                    row.get("rmnote")
                ),
            }

            transactions.append(transaction)

    return transactions



# ============================================================
# 591 歷史成交資料
# ============================================================

def load_591_transactions():
    """讀取 data/591_transactions.csv，轉成與官方實價相同的內部格式。"""
    path = find_file("591_transactions.csv")
    if not path:
        print("⚠️ 找不到 data/591_transactions.csv，將只使用官方實價資料。")
        return []

    transactions = []
    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            district = clean_text(row.get("district"))
            if district not in {"士林區", "北投區"}:
                continue

            area = to_float(row.get("building_area"))
            unit_price = to_float(row.get("unit_price"))
            if area is None or area <= 0 or unit_price is None or unit_price <= 0:
                continue

            location = clean_text(row.get("address"))
            if not location:
                continue

            transactions.append({
                "id": clean_text(row.get("transaction_id")),
                "source": "591",
                "district": district,
                "location": location,
                "street": extract_street(location),
                "building_type": normalize_building_type(row.get("building_type")),
                "area": area,
                "unit_price": unit_price,
                "transaction_price": to_float(row.get("total_price")),
                "date": clean_text(row.get("transaction_date")),
                "age": to_float(row.get("age")),
                "floor": clean_text(row.get("floor")),
                "total_floors": clean_text(row.get("total_floors")),
                "rooms": clean_text(row.get("rooms")),
                "parking_price": to_float(row.get("parking_price")),
                "parking_area": to_float(row.get("parking_area")),
                "address_key": address_key(location),
                "unit_key": exact_unit_key(location, row.get("floor")),
                "case_f": "房地",
                "building_name": clean_text(row.get("building_name")),
                "remark": clean_text(row.get("remark")),
            })

    print(f"591 歷史成交：{len(transactions)} 筆")
    return transactions


# ============================================================
# 第21階段：地址／樓層／車位校正工具
# ============================================================

CHINESE_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3,
    "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    "十": 10,
}


def normalize_chinese_number(value):
    """將常見中文數字轉成阿拉伯數字，例如 六 -> 6、十二 -> 12。"""
    text = clean_text(value)
    if not text:
        return ""

    if text.isdigit():
        return text

    if text == "十":
        return "10"

    if "十" in text:
        parts = text.split("十")
        tens = 1 if parts[0] == "" else CHINESE_DIGITS.get(parts[0], None)
        ones = 0 if len(parts) == 1 or parts[1] == "" else CHINESE_DIGITS.get(parts[1], None)
        if tens is not None and ones is not None:
            return str(tens * 10 + ones)

    if text in CHINESE_DIGITS:
        return str(CHINESE_DIGITS[text])

    return text


def normalize_address(value):
    """
    統一地址格式，去除空白與常見分隔符。
    不自行改動門牌號，只做字串標準化。
    """
    text = normalize_location(value)
    text = re.sub(r"\s+", "", text)
    text = text.replace("臺", "台")
    text = text.replace("之", "-")
    text = text.replace("巷", "巷")
    text = text.replace("弄", "弄")
    text = text.replace("號", "號")
    return text


def extract_house_number(location):
    """抓取主要門牌，例如 德行西路88號6樓之1 -> 88。"""
    text = normalize_address(location)
    match = re.search(r"(\d+)\s*號", text)
    return match.group(1) if match else ""


def extract_floor_key(value):
    """
    將 6F、6樓、六樓、6層 等格式統一成 6。
    若是 6樓之1，仍回傳 6；房號另由地址字串保留。
    """
    text = clean_text(value).upper().replace(" ", "")
    match = re.search(r"(\d+)\s*(?:F|樓|層)", text)
    if match:
        return match.group(1)

    match = re.search(r"([一二三四五六七八九十兩〇零]+)\s*(?:樓|層)", text)
    if match:
        return normalize_chinese_number(match.group(1))

    if text.isdigit():
        return text

    return ""


def extract_floor_from_location(location):
    return extract_floor_key(location)


def address_key(location):
    """
    主要地址鍵：路段＋門牌。
    用於「同地址」最高優先級比價。
    """
    street = extract_street(location)
    number = extract_house_number(location)
    if street and number:
        return f"{street}{number}號"
    return normalize_address(location)


def exact_unit_key(location, floor):
    """
    同門牌＋同樓層鍵。
    例如：德行西路88號＋6樓 -> 德行西路88號|6
    """
    return f"{address_key(location)}|{extract_floor_from_location(floor) or extract_floor_from_location(location)}"


def listing_net_unit_price(listing):
    """
    在售物件價格校正：
    若資料同時有總價、車位價、建物坪數、車位坪數，
    以「扣車位後」方式計算可與實價 uprice 比較的單價。
    若缺少必要欄位，退回原 unit_price。
    """
    total = listing.get("total_price")
    parking_price = listing.get("parking_price")
    area = listing.get("building_area")
    parking_area = listing.get("parking_area")

    if (
        total is not None and total > 0
        and parking_price is not None and parking_price >= 0
        and area is not None and area > 0
        and parking_area is not None and 0 <= parking_area < area
    ):
        return (total - parking_price) / (area - parking_area)

    return listing.get("unit_price")


def transaction_net_unit_price(transaction):
    """
    實價資料的 uprice 視為政府資料已提供的比較單價。
    不再重複扣車位，避免把 85.8 萬/坪這類「已扣車位」資料再次扣除。
    """
    return transaction.get("unit_price")


# ============================================================
# 成交匹配
# ============================================================

def area_difference_ratio(listing_area, transaction_area):
    if listing_area <= 0:
        return 999

    return abs(
        transaction_area - listing_area
    ) / listing_area



def community_key(value):
    """只使用來源明確提供的社區／建物名稱，不從行銷標題猜名稱。"""
    text = clean_text(value)
    if not text:
        return ""
    text = re.sub(r"\s+", "", text).replace("臺", "台")
    return text


def life_circle_key(street):
    """保守建立生活圈鍵值；不以同行政區直接冒充生活圈。"""
    text = clean_text(street)
    if not text:
        return ""
    text = re.sub(r"[一二三四五六七八九十百0-9]+段$", "", text)
    text = re.sub(r"[一二三四五六七八九十百0-9]+$", "", text)

    if "德行東路" in text or "德行西路" in text:
        return "德行生活圈"
    if "中山北路" in text:
        return "中山北路生活圈"
    if "忠誠路" in text:
        return "忠誠路生活圈"
    if "天母東路" in text or "天母西路" in text:
        return "天母生活圈"
    if "士東路" in text or "士商路" in text:
        return "士東生活圈"
    if "石牌路" in text or "裕民路" in text:
        return "石牌生活圈"
    if "文林路" in text:
        return "士林生活圈"
    if "承德路" in text:
        return "承德生活圈"
    if "北投路" in text or "大興街" in text or "中央北路" in text:
        return "北投生活圈"
    return text


def floor_ratio(value, total_floors):
    """樓層位置比例，缺資料時回傳 None。"""
    floor = extract_floor_key(value)
    total = to_float(total_floors)
    if not floor or total is None or total <= 0:
        return None
    try:
        return int(floor) / total
    except (TypeError, ValueError):
        return None


def parking_flag(obj):
    """判斷是否有車位資料／車位。"""
    parking = clean_text(obj.get("parking"))
    if parking:
        return parking not in {"無", "無車位", "沒有"}
    return obj.get("parking_price") is not None or obj.get("parking_area") is not None


def age_adjustment(listing, transaction):
    """屋齡校正：標的較新時，成交單價向上校正；每差1年約0.8%，上限±12%。"""
    la = to_float(listing.get("age"))
    ta = to_float(transaction.get("age"))
    if la is None or ta is None:
        return 1.0
    diff = ta - la
    return max(0.88, min(1.12, 1.0 + diff * 0.008))


def transaction_time_adjustment(transaction):
    """
    成交時間校正：以目前日期為基準，舊成交逐步降低權重/價格。
    這裡採保守年化2.0%趨勢調整，最多±8%，避免把歷史價格硬套到現在。
    """
    date_text = clean_text(transaction.get("date"))
    if not date_text:
        return 1.0
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d").date()
        today = datetime.now().date()
        years = max(0.0, (today - dt).days / 365.25)
        return max(0.92, min(1.08, 1.0 + years * 0.02))
    except Exception:
        return 1.0


def recency_weight(transaction):
    """近期成交權重較高，最多1.0，最低0.55。"""
    date_text = clean_text(transaction.get("date"))
    if not date_text:
        return 0.55
    try:
        dt = datetime.strptime(date_text, "%Y-%m-%d").date()
        days = max(0, (datetime.now().date() - dt).days)
        return round(max(0.55, math.exp(-days / 730.0)), 4)
    except Exception:
        return 0.55


def floor_adjustment(listing, transaction):
    """樓層小幅校正；上限±8%。"""
    lr = floor_ratio(listing.get("floor"), listing.get("total_floors"))
    tr = floor_ratio(transaction.get("floor"), transaction.get("total_floors"))
    if lr is not None and tr is not None:
        return max(0.92, min(1.08, 1.0 + (lr - tr) * 0.12))

    lf = extract_floor_key(listing.get("floor"))
    tf = extract_floor_key(transaction.get("floor"))
    if lf and tf:
        try:
            return max(0.94, min(1.06, 1.0 + (int(lf) - int(tf)) * 0.01))
        except ValueError:
            pass
    return 1.0


def parking_adjustment(listing, transaction):
    """
    不自行猜車位價格；若一方有車位、一方沒有，只降低可比權重，
    不直接把未知車位價硬加減到成交單價。
    """
    return 1.0


def area_adjustment(listing, transaction):
    """坪數差異只做溫和修正，最多±5%。"""
    la = to_float(listing.get("building_area"))
    ta = to_float(transaction.get("area"))
    if la is None or ta is None or la <= 0 or ta <= 0:
        return 1.0
    ratio = (ta - la) / la
    return max(0.95, min(1.05, 1.0 + ratio * 0.20))


def adjusted_transaction_unit_price(listing, transaction):
    """成交單價依屋齡／樓層／坪數／成交時間做保守校正。"""
    price = transaction_net_unit_price(transaction)
    if price is None or price <= 0:
        return None
    return (
        price
        * age_adjustment(listing, transaction)
        * floor_adjustment(listing, transaction)
        * area_adjustment(listing, transaction)
        * parking_adjustment(listing, transaction)
        * transaction_time_adjustment(transaction)
    )


def weighted_mean(values_weights):
    if not values_weights:
        return None
    total_w = sum(w for _, w in values_weights if w > 0)
    if total_w <= 0:
        return None
    return sum(v * w for v, w in values_weights if w > 0) / total_w


def weighted_median(values_weights):
    if not values_weights:
        return None
    pairs = sorted((v, w) for v, w in values_weights if w > 0)
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if acc >= total_w / 2:
            return value
    return pairs[-1][0]


def weighted_percentile(values_weights, p):
    if not values_weights:
        return None
    pairs = sorted((v, w) for v, w in values_weights if w > 0)
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    target = total_w * p
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if acc >= target:
            return value
    return pairs[-1][0]


def parking_value_for_listing(listing):
    """取得車位價格；缺資料時不猜測。"""
    value = to_float(listing.get("parking_price"))
    return value if value is not None and value >= 0 else 0.0


def total_price_from_unit_price(listing, unit_price):
    """
    將房屋本體單價轉回總價：
    房屋本體單價 ×（建物坪數－車位坪數）＋車位價。
    若缺車位坪數，退回建物坪數計算。
    單位：萬元。
    """
    if unit_price is None:
        return None
    area = to_float(listing.get("building_area"))
    if area is None or area <= 0:
        return None
    parking_area = to_float(listing.get("parking_area"))
    if parking_area is not None and 0 <= parking_area < area:
        base_area = area - parking_area
    else:
        base_area = area
    return unit_price * base_area + parking_value_for_listing(listing)


def price_band_from_market(listing, market_median, q1, q3, sample_count):
    """產生房仲實戰五段價格。"""
    if market_median is None or sample_count < 3:
        return {
            "current_asking_price": round_number(listing.get("total_price")),
            "market_fair_price_low": None,
            "market_fair_price_high": None,
            "reasonable_transaction_price_low": None,
            "reasonable_transaction_price_high": None,
            "buyer_offer_low": None,
            "buyer_offer_high": None,
            "seller_floor_low": None,
            "seller_floor_high": None,
            "confidence": "低",
            "note": "成交樣本不足3筆，不輸出精確議價價格。"
        }

    fair_low_u = q1 if q1 is not None else market_median * 0.95
    fair_high_u = q3 if q3 is not None else market_median * 1.05

    # 合理成交區間以市場中位數附近的保守帶為主
    tx_low_u = market_median * 0.97
    tx_high_u = market_median * 1.03

    # 買方起手價略低於合理成交中位
    buyer_low_u = market_median * 0.90
    buyer_high_u = market_median * 0.95

    # 賣方底價以合理成交區間下緣附近為參考
    seller_low_u = market_median * 0.95
    seller_high_u = market_median * 1.00

    confidence = "高" if sample_count >= 8 else ("中" if sample_count >= 5 else "中低")

    return {
        "current_asking_price": round_number(listing.get("total_price")),
        "market_fair_price_low": round_number(total_price_from_unit_price(listing, fair_low_u)),
        "market_fair_price_high": round_number(total_price_from_unit_price(listing, fair_high_u)),
        "reasonable_transaction_price_low": round_number(total_price_from_unit_price(listing, tx_low_u)),
        "reasonable_transaction_price_high": round_number(total_price_from_unit_price(listing, tx_high_u)),
        "buyer_offer_low": round_number(total_price_from_unit_price(listing, buyer_low_u)),
        "buyer_offer_high": round_number(total_price_from_unit_price(listing, buyer_high_u)),
        "seller_floor_low": round_number(total_price_from_unit_price(listing, seller_low_u)),
        "seller_floor_high": round_number(total_price_from_unit_price(listing, seller_high_u)),
        "confidence": confidence,
        "note": "價格為資料模型推估，仍需搭配屋況、裝潢、採光、棟別、車位型式及屋主出售急迫性判斷。"
    }


def classify_comparable_level(listing, transaction):
    """
    五級比價：
    A 同門牌＋同樓層
    B 同門牌／同棟／同社區
    C 同路段高度可比
    D 同生活圈行情參考
    E 排除
    """
    if listing["district"] != transaction["district"]:
        return "E", "不同行政區"

    listing_address = listing.get("address_key") or address_key(listing["location"])
    transaction_address = transaction.get("address_key") or address_key(transaction["location"])

    listing_unit = listing.get("unit_key") or exact_unit_key(
        listing["location"], listing.get("floor")
    )
    transaction_unit = transaction.get("unit_key") or exact_unit_key(
        transaction["location"], transaction.get("floor")
    )

    same_unit = bool(
        listing_unit and transaction_unit
        and listing_unit == transaction_unit
        and listing_address == transaction_address
    )
    same_address = bool(
        listing_address and transaction_address
        and listing_address == transaction_address
    )

    listing_building = community_key(listing.get("building_name"))
    transaction_building = community_key(transaction.get("building_name"))
    same_building = bool(
        listing_building and transaction_building
        and listing_building == transaction_building
    )

    area_ratio = area_difference_ratio(listing["building_area"], transaction["area"])
    if area_ratio > 0.25:
        return "E", "坪數差異超過25%"

    listing_type = normalize_building_type(listing.get("building_type"))
    transaction_type = transaction.get("building_type", "未知")
    same_type = (
        listing_type != "未知"
        and transaction_type != "未知"
        and listing_type == transaction_type
    )

    if same_unit:
        return "A", "同門牌＋同樓層"
    if same_address or same_building:
        return "B", "同門牌／同棟／同社區"

    same_street = bool(
        listing.get("street")
        and transaction.get("street")
        and listing["street"] == transaction["street"]
    )
    if same_street and same_type:
        return "C", "同路段＋同類型"
    if same_street and area_ratio <= 0.15:
        return "C", "同路段＋坪數高度接近"

    listing_circle = life_circle_key(listing.get("street"))
    transaction_circle = life_circle_key(transaction.get("street"))
    if (
        listing_circle
        and transaction_circle
        and listing_circle == transaction_circle
        and same_type
        and area_ratio <= 0.20
    ):
        return "D", "同生活圈行情參考"

    return "E", "可比條件不足"


def comparable_weight(level, score):
    """D級只做行情背景，不進主要估價中位數。"""
    base = {"A": 1.00, "B": 0.90, "C": 0.75, "D": 0.45, "E": 0.0}.get(level, 0.0)
    return round(base * max(0.5, min(1.2, score / 100.0)), 4)


def transaction_score(listing, transaction):
    """第25階段多層級比價評分。"""
    level, _ = classify_comparable_level(listing, transaction)
    if level == "E":
        return -1

    area_ratio = area_difference_ratio(listing["building_area"], transaction["area"])
    score = {"A": 260, "B": 190, "C": 120, "D": 60}.get(level, -1)

    if area_ratio <= 0.10:
        score += 30
    elif area_ratio <= 0.20:
        score += 18
    elif area_ratio <= 0.25:
        score += 5

    listing_type = normalize_building_type(listing.get("building_type"))
    transaction_type = transaction.get("building_type", "未知")
    if (
        listing_type != "未知"
        and transaction_type != "未知"
        and listing_type == transaction_type
    ):
        score += 25

    lf = extract_floor_key(listing.get("floor"))
    tf = extract_floor_key(transaction.get("floor"))
    if lf and tf:
        try:
            diff = abs(int(lf) - int(tf))
            if diff == 0:
                score += 20
            elif diff == 1:
                score += 10
            elif diff == 2:
                score += 5
        except ValueError:
            pass

    if parking_flag(listing) == parking_flag(transaction):
        score += 8

    return score


def find_comparables(listing, transactions, max_results=20):
    """
    A/B/C = 主要可比樣本；D = 行情參考；E = 排除。
    不同街道不直接混入主要比價，坪數超過±25%直接排除。
    """
    candidates = []

    for transaction in transactions:
        level, reason = classify_comparable_level(listing, transaction)
        if level == "E":
            continue

        score = transaction_score(listing, transaction)
        if score < 0:
            continue

        candidates.append(
            {
                "level": level,
                "score": score,
                "reason": reason,
                "weight": comparable_weight(level, score),
                "transaction": transaction,
            }
        )

    candidates.sort(
        key=lambda x: (
            {"A": 0, "B": 1, "C": 2, "D": 3}.get(x["level"], 9),
            -x["score"],
            area_difference_ratio(listing["building_area"], x["transaction"]["area"]),
            x["transaction"].get("date", ""),
        )
    )

    primary = [x for x in candidates if x["level"] in {"A", "B", "C"}]
    reference = [x for x in candidates if x["level"] == "D"]

    return {
        "primary": primary[:max_results],
        "reference": reference[:max_results],
        "all": candidates[:max_results * 2],
    }


# ============================================================
# 市場判斷
# ============================================================

def classify_market(premium, sample_count=0):
    """
    正式市場判定必須同時滿足：
    1. 有成交資料
    2. 至少3筆可比成交

    樣本不足時，即使單筆成交與開價差距非常大，
    也不得產生「高於市場」等正式判定。
    """
    if premium is None or sample_count < 3:
        return {
            "level": "樣本不足",
            "emoji": "⚪",
            "description": (
                f"目前僅有 {sample_count} 筆有效可比成交，"
                "不足以進行正式市場溢價／折價判定"
            ),
        }

    if premium <= -0.08:
        return {
            "level": "低於市場",
            "emoji": "🟢",
            "description": "目前開價低於附近成交行情，具備價格吸引力",
        }

    if premium <= 0.05:
        return {
            "level": "接近市場",
            "emoji": "🟡",
            "description": "目前開價大致落在附近成交行情合理範圍",
        }

    if premium <= 0.12:
        return {
            "level": "合理偏高",
            "emoji": "🟡",
            "description": "目前開價高於附近成交行情，仍有議價空間",
        }

    return {
        "level": "高於市場",
        "emoji": "🔴",
        "description": "目前開價明顯高於附近成交行情",
    }


def calculate_recommendations(
    listing,
    market_median,
    q1,
    q3,
    sample_count
):
    """
    嚴格樣本門檻：
    - 0～2筆：不提供精確買方／賣方價格
    - 3～4筆：可提供初步參考，但明確標示樣本有限
    - 5筆以上：可作主要議價參考之一
    """
    if market_median is None or sample_count < 3:
        return {
            "seller_price_low": None,
            "seller_price_high": None,
            "buyer_price_low": None,
            "buyer_price_high": None,
            "note": (
                "成交樣本不足3筆，暫不提供精確議價價格；"
                "請優先補充同門牌、同社區或同路段成交案例。"
            ),
        }

    seller_low = q1
    seller_high = q3

    buyer_low = market_median * 0.92
    buyer_high = market_median * 0.97

    if sample_count < 5:
        note = "成交樣本3～4筆，僅作初步議價參考，仍應搭配屋況、樓層與車位條件。"
    else:
        note = "成交樣本達5筆以上，可作為主要議價參考之一。"

    return {
        "seller_price_low": round_number(seller_low),
        "seller_price_high": round_number(seller_high),
        "buyer_price_low": round_number(buyer_low),
        "buyer_price_high": round_number(buyer_high),
        "note": note,
    }


def analyze_listing(listing, transactions):
    comparable_data = find_comparables(listing, transactions)
    primary = comparable_data["primary"]
    reference = comparable_data["reference"]

    def price_rows(items):
        rows = []
        for item in items:
            price = adjusted_transaction_unit_price(listing, item["transaction"])
            if price is not None and price > 0:
                # 樣本權重 = 比價層級 × 相似度 × 近期性
                base_weight = item["weight"]
                time_weight = recency_weight(item["transaction"])
                final_weight = round(base_weight * time_weight, 4)
                rows.append((item, price, final_weight))
        return rows

    primary_rows = price_rows(primary)
    reference_rows = price_rows(reference)

    weighted_prices = [(price, weight) for _, price, weight in primary_rows]
    reference_weighted_prices = [(price, weight) for _, price, weight in reference_rows]

    prices = [price for price, _ in weighted_prices]
    sample_count = len(prices)
    normalized_listing_price = listing_net_unit_price(listing)

    market_average = weighted_mean(weighted_prices)
    market_median = weighted_median(weighted_prices)
    q1 = weighted_percentile(weighted_prices, 0.25)
    q3 = weighted_percentile(weighted_prices, 0.75)

    reference_average = weighted_mean(reference_weighted_prices)
    reference_median = weighted_median(reference_weighted_prices)

    comparable_rows = build_comparable_rows(
        listing,
        [(item, price, weight) for item, price, weight in primary_rows],
        is_reference=False
    )
    reference_rows_out = build_comparable_rows(
        listing,
        [(item, price, weight) for item, price, weight in reference_rows],
        is_reference=True
    )

    tier_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for item in primary + reference:
        if item["level"] in tier_counts:
            tier_counts[item["level"]] += 1

    same_address_count = sum(1 for row in comparable_rows if row["same_address"])
    same_unit_count = sum(1 for row in comparable_rows if row["same_unit"])

    if not prices:
        return {
            "listing": listing,
            "comparison": {
                "sample_count": 0,
                "primary_sample_count": 0,
                "reference_sample_count": len(reference_weighted_prices),
                "market_average": None,
                "market_median": None,
                "q1": None,
                "q3": None,
                "reference_average": round_number(reference_average) if reference_average is not None else None,
                "reference_median": round_number(reference_median) if reference_median is not None else None,
                "listing_unit_price": round_number(normalized_listing_price),
                "raw_listing_unit_price": round_number(listing.get("unit_price")),
                "premium_ratio": None,
                "premium_percent": None,
                "market": classify_market(None, 0),
                "recommendations": calculate_recommendations(listing, None, None, None, 0),
                "pricing_engine": price_band_from_market(listing, None, None, None, 0),
                "same_address_count": same_address_count,
                "same_unit_count": same_unit_count,
                "tier_counts": tier_counts,
                "comparables": [],
                "reference_comparables": reference_rows_out,
            },
        }

    premium_ratio = None
    premium_percent = None
    if sample_count >= 3 and normalized_listing_price is not None and market_median:
        premium_ratio = (normalized_listing_price - market_median) / market_median
        premium_percent = premium_ratio * 100

    market = classify_market(premium_ratio, sample_count)
    recommendations = calculate_recommendations(
        listing, market_median, q1, q3, sample_count
    )
    pricing_engine = price_band_from_market(
        listing, market_median, q1, q3, sample_count
    )

    return {
        "listing": listing,
        "comparison": {
            "sample_count": sample_count,
            "primary_sample_count": sample_count,
            "reference_sample_count": len(reference_weighted_prices),
            "market_average": round_number(market_average),
            "market_median": round_number(market_median),
            "q1": round_number(q1),
            "q3": round_number(q3),
            "reference_average": round_number(reference_average) if reference_average is not None else None,
            "reference_median": round_number(reference_median) if reference_median is not None else None,
            "listing_unit_price": round_number(normalized_listing_price),
            "raw_listing_unit_price": round_number(listing.get("unit_price")),
            "premium_ratio": round_number(premium_ratio, 4),
            "premium_percent": round_number(premium_percent),
            "market": market,
            "recommendations": recommendations,
            "pricing_engine": pricing_engine,
            "same_address_count": same_address_count,
            "same_unit_count": same_unit_count,
            "tier_counts": tier_counts,
            "comparables": comparable_rows,
            "reference_comparables": reference_rows_out,
        },
    }


def build_comparable_rows(listing, rows, is_reference=False):
    result = []
    listing_address = listing.get("address_key") or address_key(listing["location"])
    listing_unit = listing.get("unit_key") or exact_unit_key(
        listing["location"], listing.get("floor")
    )

    for item, adjusted_price, final_weight in rows:
        transaction = item["transaction"]
        transaction_address = transaction.get("address_key") or address_key(transaction["location"])
        transaction_unit = transaction.get("unit_key") or exact_unit_key(
            transaction["location"], transaction.get("floor")
        )

        same_address = bool(
            listing_address and transaction_address
            and listing_address == transaction_address
        )
        same_unit = bool(
            same_address and listing_unit and transaction_unit
            and listing_unit == transaction_unit
        )

        result.append(
            {
                "score": item["score"],
                "tier": item["level"],
                "tier_reason": item["reason"],
                "weight": item["weight"],
                "final_weight": final_weight,
                "age_adjustment": round_number(age_adjustment(listing, transaction), 4),
                "floor_adjustment": round_number(floor_adjustment(listing, transaction), 4),
                "area_adjustment": round_number(area_adjustment(listing, transaction), 4),
                "time_adjustment": round_number(transaction_time_adjustment(transaction), 4),
                "recency_weight": round_number(recency_weight(transaction), 4),
                "reference_only": is_reference,
                "source": transaction.get("source", "MOI"),
                "match_level": (
                    "A｜同門牌＋同樓層"
                    if item["level"] == "A"
                    else "B｜同門牌／同棟／同社區"
                    if item["level"] == "B"
                    else "C｜同路段高度可比"
                    if item["level"] == "C"
                    else "D｜同生活圈行情參考"
                ),
                "same_address": same_address,
                "same_unit": same_unit,
                "date": transaction["date"],
                "location": transaction["location"],
                "street": transaction["street"],
                "building_type": transaction["building_type"],
                "area": round_number(transaction["area"]),
                "unit_price": round_number(transaction_net_unit_price(transaction)),
                "adjusted_unit_price": round_number(adjusted_price),
                "transaction_price": round_number(transaction["transaction_price"]),
                "parking_price": round_number(transaction.get("parking_price")),
                "parking_area": round_number(transaction.get("parking_area")),
                "building_name": transaction["building_name"],
            }
        )

    return result


# ============================================================
# 整體分析
# ============================================================

def build_report(
    listings,
    transactions
):
    results = []

    for listing in listings:

        result = analyze_listing(
            listing,
            transactions
        )

        results.append(result)

    # ========================================================
    # 市場摘要
    # ========================================================

    total = len(results)

    low_count = 0
    near_count = 0
    high_count = 0
    unknown_count = 0

    for result in results:

        level = result[
            "comparison"
        ][
            "market"
        ][
            "level"
        ]

        if level == "低於市場":
            low_count += 1

        elif level in {
            "接近市場",
            "合理偏高"
        }:
            near_count += 1

        elif level == "高於市場":
            high_count += 1

        else:
            unknown_count += 1

    return {
        "generated_at": datetime.now().astimezone().isoformat(),

        "stage": "第26階段：多層級比價＋房仲實戰定價引擎（A/B/C主要比價＋D行情參考＋E排除）",

        "summary": {
            "listing_count": total,
            "transaction_count": len(
                transactions
            ),
            "moi_transaction_count": sum(
                1 for tx in transactions if tx.get("source") == "MOI"
            ),
            "591_transaction_count": sum(
                1 for tx in transactions if tx.get("source") == "591"
            ),
            "below_market": low_count,
            "near_market": near_count,
            "above_market": high_count,
            "insufficient_sample": unknown_count
        },

        "results": results
    }


# ============================================================
# 儲存 JSON
# ============================================================

def save_report(report):

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "第26階段：多層級比價＋房仲實戰定價引擎（A/B/C主要比價＋D行情參考＋Runner 路徑自動搜尋）"
    )
    print("=" * 70)

    print()
    print(f"專案根目錄：{BASE_DIR}")
    print(f"在售資料：{LISTING_FILE}")
    print(f"成交資料：{TRANSACTION_FILE}")
    print("讀取在售物件……")

    listings = load_listings()

    print(
        f"在售物件：{len(listings)} 筆"
    )

    print()
    print("讀取官方實價成交資料……")

    moi_transactions = load_transactions()
    for tx in moi_transactions:
        tx["source"] = "MOI"

    print(f"官方實價住宅買賣成交：{len(moi_transactions)} 筆")

    print()
    print("讀取 591 歷史成交資料……")

    transactions_591 = load_591_transactions()
    print(f"591 歷史成交：{len(transactions_591)} 筆")

    transactions = moi_transactions + transactions_591

    print()
    print(f"合併後有效成交：{len(transactions)} 筆")
    print("開始進行市場比價……")

    report = build_report(
        listings,
        transactions
    )

    save_report(report)

    print()
    print("=" * 70)
    print("第26階段完成")
    print("=" * 70)

    print()
    print(
        f"在售物件："
        f"{report['summary']['listing_count']} 筆"
    )

    print(
        f"成交比較資料："
        f"{report['summary']['transaction_count']} 筆"
    )
    print(
        f"其中官方實價：{report['summary']['moi_transaction_count']} 筆；"
        f"591：{report['summary']['591_transaction_count']} 筆"
    )

    print(
        f"🟢 低於市場："
        f"{report['summary']['below_market']} 筆"
    )

    print(
        f"🟡 接近／合理偏高："
        f"{report['summary']['near_market']} 筆"
    )

    print(
        f"🔴 高於市場："
        f"{report['summary']['above_market']} 筆"
    )

    print(
        f"⚪ 樣本不足："
        f"{report['summary']['insufficient_sample']} 筆"
    )

    print()
    print(
        f"輸出檔案：{OUTPUT_FILE}"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
