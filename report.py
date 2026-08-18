# -*- coding: utf-8 -*-

"""
第九階段：每日房市專業報告

功能：
1. 讀取 data/taipei_transactions.csv
2. 分析士林區／北投區
3. 產生 HTML 房市報告
4. 產生 JSON 房市資料
5. 自動建立 reports 資料夾
6. 產生 latest.html
"""

import csv
import json
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from statistics import mean, median


# ============================================================
# 基本設定
# ============================================================

INPUT_FILE = "data/taipei_transactions.csv"
REPORT_DIR = "reports"

TARGET_DISTRICTS = [
    "士林區",
    "北投區",
]


# ============================================================
# 數字轉換
# ============================================================

def to_float(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = (
        text
        .replace(",", "")
        .replace("，", "")
    )

    try:
        return float(text)

    except (ValueError, TypeError):
        return None


# ============================================================
# 日期解析
# ============================================================

def parse_date(value):

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # 去除日期後面的時間
    text = text.split(" ")[0]

    # ========================================================
    # 純數字日期
    #
    # 民國：
    # 1150528 → 2026-05-28
    #
    # 西元：
    # 20260528 → 2026-05-28
    # ========================================================

    compact = re.sub(
        r"[^0-9]",
        "",
        text
    )

    # --------------------------------------------------------
    # 民國 7 碼
    # 例如：1150528
    # --------------------------------------------------------

    if re.fullmatch(
        r"\d{7}",
        compact
    ):

        year = (
            int(compact[:3])
            + 1911
        )

        month = int(
            compact[3:5]
        )

        day = int(
            compact[5:7]
        )

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            pass

    # --------------------------------------------------------
    # 西元 8 碼
    # 例如：20260528
    # --------------------------------------------------------

    if re.fullmatch(
        r"\d{8}",
        compact
    ):

        year = int(
            compact[:4]
        )

        month = int(
            compact[4:6]
        )

        day = int(
            compact[6:8]
        )

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            pass

    # ========================================================
    # 一般日期格式
    # ========================================================

    text = (
        text
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", "")
        .replace("/", "-")
        .replace(".", "-")
    )

    # ========================================================
    # 民國日期
    #
    # 例如：
    # 115-05-28
    # ========================================================

    match = re.match(
        r"^(\d{2,3})-(\d{1,2})-(\d{1,2})$",
        text
    )

    if match:

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        day = int(
            match.group(3)
        )

        if year < 1911:

            year += 1911

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            return None

    # ========================================================
    # 西元日期
    #
    # 例如：
    # 2026-05-28
    # ========================================================

    match = re.match(
        r"^(\d{4})-(\d{1,2})-(\d{1,2})$",
        text
    )

    if match:

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        day = int(
            match.group(3)
        )

        try:

            datetime(
                year,
                month,
                day
            )

            return (
                year,
                month,
                day
            )

        except ValueError:

            return None

    return None


# ============================================================
# 找交易日期
# ============================================================

def get_transaction_date(row):

    fields = [
        "sdate",
        "fdate",
        "transaction_date",
        "trade_date",
        "date",
    ]

    for field in fields:

        parsed = parse_date(
            row.get(field)
        )

        if parsed:
            return parsed

    return None


# ============================================================
# 路段
# ============================================================

# ============================================================
# 路段
# ============================================================

def extract_route(location):

    if not location:
        return "未知路段"

    text = str(location).strip()

    # --------------------------------------------------------
    # 移除行政區前綴
    #
    # 例如：
    # 台北市士林區天母西路50號
    # ↓
    # 天母西路50號
    #
    # 台北市北投區中山北路七段20號
    # ↓
    # 中山北路七段20號
    # --------------------------------------------------------

    text = re.sub(
        r"^.*?(?:士林區|北投區)",
        "",
        text
    )

    # --------------------------------------------------------
    # 找出道路名稱
    #
    # 可以辨識：
    # 天母西路
    # 德行東路
    # 中山北路六段
    # 承德路七段
    # 克強路
    # 美崙街
    # --------------------------------------------------------

    pattern = (
        r"[\u4e00-\u9fff]{2,10}"
        r"(?:路|街|大道)"
        r"(?:[0-9一二三四五六七八九十百]+段)?"
    )

    match = re.search(
        pattern,
        text
    )

    if match:
        return match.group(0)

    return "其他"


# ============================================================
# 讀取 CSV
# ============================================================

def load_records():

    if not os.path.exists(INPUT_FILE):

        print(
            f"找不到資料檔案：{INPUT_FILE}"
        )

        return []

    records = []

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            district = str(
                row.get("district", "")
            ).strip()

            if district not in TARGET_DISTRICTS:
                continue

            case_type = str(
                row.get("case_t", "")
            ).strip()

            if case_type != "買賣":
                continue

            unit_price = to_float(
                row.get("uprice")
            )

            total_price = to_float(
                row.get("price")
            )

            if total_price is None:

                total_price = to_float(
                    row.get("tprice")
                )

            area = to_float(
                row.get("farea")
            )

            if (
                unit_price is None
                or unit_price <= 0
                or total_price is None
                or total_price <= 0
                or area is None
                or area <= 0
            ):
                continue

            records.append({

                "row": row,

                "district": district,

                "unit_price": unit_price,

                "total_price": total_price,

                "area": area,

                "route": extract_route(
                    row.get("location", "")
                ),

                "date": get_transaction_date(
                    row
                ),

            })

    return records


# ============================================================
# IQR
# ============================================================

def percentile(values, percent):

    if not values:
        return None

    data = sorted(values)

    if len(data) == 1:
        return data[0]

    position = (
        (len(data) - 1)
        * percent
    )

    lower = int(position)

    upper = lower + 1

    if upper >= len(data):

        return data[lower]

    weight = position - lower

    return (
        data[lower]
        * (1 - weight)
        +
        data[upper]
        * weight
    )


# ============================================================
# 行政區統計
# ============================================================

def analyze_district(items):

    prices = [
        item["unit_price"]
        for item in items
    ]

    totals = [
        item["total_price"]
        for item in items
    ]

    areas = [
        item["area"]
        for item in items
    ]

    q1 = percentile(
        prices,
        0.25
    )

    q3 = percentile(
        prices,
        0.75
    )

    if q1 is not None and q3 is not None:

        iqr = q3 - q1

        lower = q1 - 1.5 * iqr

        upper = q3 + 1.5 * iqr

    else:

        lower = None
        upper = None

    normal = []

    abnormal = []

    for item in items:

        if (
            lower is not None
            and upper is not None
            and (
                item["unit_price"] < lower
                or
                item["unit_price"] > upper
            )
        ):

            abnormal.append(item)

        else:

            normal.append(item)

    normal_prices = [
        item["unit_price"]
        for item in normal
    ]

    return {

        "count": len(items),

        "average_price":
            mean(prices),

        "median_price":
            median(prices),

        "max_price":
            max(prices),

        "min_price":
            min(prices),

        "average_total":
            mean(totals),

        "average_area":
            mean(areas),

        "normal_average":
            mean(normal_prices)
            if normal_prices
            else None,

        "abnormal_count":
            len(abnormal),

        "q1": q1,

        "q3": q3,

        "iqr_lower": lower,

        "iqr_upper": upper,

    }


# ============================================================
# 月份趨勢
# ============================================================

def monthly_trend(items):

    groups = {}

    for item in items:

        date_value = item["date"]

        if not date_value:
            continue

        year, month, day = date_value

        key = (
            year,
            month
        )

        if key not in groups:

            groups[key] = []

        groups[key].append(
            item["unit_price"]
        )

    months = sorted(
        groups.keys()
    )

    result = []

    previous = None

    for year, month in months:

        prices = groups[
            (year, month)
        ]

        average_price = mean(
            prices
        )

        change = None

        if (
            previous is not None
            and previous != 0
        ):

            change = (
                (
                    average_price
                    - previous
                )
                / previous
                * 100
            )

        result.append({

            "month":
                f"{year:04d}-{month:02d}",

            "count":
                len(prices),

            "average":
                average_price,

            "median":
                median(prices),

            "change":
                change,

        })

        previous = average_price

    return result


# ============================================================
# 趨勢判斷
# ============================================================

def determine_trend(months):

    # ========================================================
    # 第10階段：
    # 改用「最近3個月」判斷市場方向
    # 避免拿多年以前的價格直接與最新月份比較
    # ========================================================

    if len(months) < 2:
        return {
            "direction": "資料不足",
            "change": None,
            "confidence": "低",
            "period": "資料不足",
            "latest_count": 0,
            "window_count": 0,
            "warning": "有效月份不足，無法判斷近期趨勢。",
        }

    # 最近3個月
    recent = months[-3:]

    latest = recent[-1]

    latest_average = latest["average"]
    latest_count = latest["count"]

    # 最近3個月交易量
    window_count = sum(
        item["count"]
        for item in recent
    )

    # ========================================================
    # 前期加權平均
    #
    # 例如：
    # 5月 16筆
    # 6月 4筆
    #
    # 會按照交易筆數加權
    # 避免單一小樣本月份影響太大
    # ========================================================

    previous_months = recent[:-1]

    previous_total_count = sum(
        item["count"]
        for item in previous_months
    )

    if previous_total_count <= 0:
        return {
            "direction": "資料不足",
            "change": None,
            "confidence": "低",
            "period": "最近3個月",
            "latest_count": latest_count,
            "window_count": window_count,
            "warning": "前期交易樣本不足。",
        }

    previous_weighted_average = (
        sum(
            item["average"] * item["count"]
            for item in previous_months
        )
        / previous_total_count
    )

    if previous_weighted_average == 0:
        return {
            "direction": "資料不足",
            "change": None,
            "confidence": "低",
            "period": "最近3個月",
            "latest_count": latest_count,
            "window_count": window_count,
            "warning": "前期價格資料不足。",
        }

    # ========================================================
    # 最近價格變化
    # ========================================================

    change = (
        (
            latest_average
            - previous_weighted_average
        )
        / previous_weighted_average
        * 100
    )

    # ========================================================
    # 趨勢方向
    # ========================================================

    if change >= 3:
        direction = "上升"

    elif change <= -3:
        direction = "下降"

    else:
        direction = "盤整"

    # ========================================================
    # 樣本可信度
    # ========================================================

    if latest_count >= 10 and window_count >= 30:

        confidence = "高"

    elif latest_count >= 5 and window_count >= 15:

        confidence = "中"

    else:

        confidence = "低"

    # ========================================================
    # 小樣本警告
    # ========================================================

    if latest_count < 5:

        warning = (
            f"最近月份僅 {latest_count} 筆交易，"
            "近期趨勢僅供參考，"
            "不宜直接解讀為整體房價走勢。"
        )

    elif latest_count < 10:

        warning = (
            f"最近月份 {latest_count} 筆交易，"
            "樣本量中等，建議搭配路段與住宅類型觀察。"
        )

    else:

        warning = (
            "最近月份樣本量相對充足，"
            "可作為近期市場方向參考。"
        )

    return {

        "direction": direction,

        "change": change,

        "confidence": confidence,

        "period": "最近3個月",

        "latest_count": latest_count,

        "window_count": window_count,

        "warning": warning,

    }


# ============================================================
# 路段熱點
# ============================================================

def route_analysis(items):

    groups = {}

    for item in items:

        route = item["route"]

        if route not in groups:

            groups[route] = []

        groups[route].append(
            item
        )

    result = []

    for route, group in groups.items():

        if len(group) < 2:

            continue

        prices = [
            item["unit_price"]
            for item in group
        ]

        average_price = mean(
            prices
        )

        heat = (
            len(group)
            * average_price
        )

        result.append({

            "route": route,

            "count": len(group),

            "average":
                average_price,

            "median":
                median(prices),

            "heat":
                heat,

        })

    result.sort(
        key=lambda x: x["heat"],
        reverse=True
    )

    return result


# ============================================================
# 建立 JSON 資料
# ============================================================

def build_report_data(records):

    report = {

        "generated_at":
            datetime.now(ZoneInfo("Asia/Taipei")).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),

        "districts": {},

    }

    for district in TARGET_DISTRICTS:

        items = [
            item
            for item in records
            if item["district"]
            == district
        ]

        if not items:
            continue

        stats = analyze_district(
            items
        )

        months = monthly_trend(
            items
        )

        trend = determine_trend(
            months
        )

        routes = route_analysis(
            items
        )

        report["districts"][
            district
        ] = {

            "stats": stats,

            "trend": trend,

            "months": months,

            "routes": routes,
            "latest_transaction_date": max(
                (item.get("date") for item in items if item.get("date")),
                default=None
            ),
            }

    return report


# ============================================================
# HTML
# ============================================================

def html_escape(value):

    text = str(value)

    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def money(value):

    if value is None:
        return "—"

    return f"{value:,.2f}"


def create_html(report):
    # ============================================================
    # 第12-1階段：士林／北投市場總覽
    # ============================================================

    summary_rows = ""

    for district, data in report["districts"].items():

        stats = data["stats"]
        trend = data["trend"]

        change = trend.get("change")

        if change is None:
            change_text = "—"
        else:
            change_text = f"{change:+.2f}%"

        summary_rows += f"""
            <tr>
                <td>
                    <strong>{html_escape(district)}</strong>
                </td>

                <td>
                    {stats["count"]:,} 筆
                </td>

                <td>
                    {money(stats["average_price"])}
                    萬／坪
                </td>

                <td>
                    {money(stats["median_price"])}
                    萬／坪
                </td>

                <td>
                    {html_escape(trend["direction"])}
                </td>

                <td>
                    {change_text}
                </td>
            </tr>
        """

    summary = f"""
        <section class="summary">

            <h2>🏠 士林區／北投區市場總覽</h2>

            <table>

                <tr>
                    <th>行政區</th>
                    <th>交易量</th>
                    <th>平均單價</th>
                    <th>中位數</th>
                    <th>市場方向</th>
                    <th>近期變化</th>
                </tr>

                {summary_rows}

            </table>

        </section>
    """
    generated_at = report[
        "generated_at"
    ]
    latest_dates = [
        data.get("latest_transaction_date")
        for data in report["districts"].values()
        if data.get("latest_transaction_date")
    ]

    latest_transaction_date = (
        max(latest_dates)
        if latest_dates
        else None
    )

    if latest_transaction_date:
        if isinstance(latest_transaction_date, tuple):
            latest_transaction_date = (
    max(latest_dates)
    if latest_dates
    else None
)

if latest_transaction_date:
    if isinstance(latest_transaction_date, tuple):
        latest_transaction_date = (
            f"{latest_transaction_date[0]}年"
            f"{latest_transaction_date[1]}月"
            f"{latest_transaction_date[2]}日"
        )
    else:
        latest_transaction_date = str(latest_transaction_date)
else:
    latest_transaction_date = "無資料"

    cards = ""

    for district, data in report[
        "districts"
    ].items():

        stats = data["stats"]

        trend = data["trend"]

        direction = trend[
            "direction"
        ]

        change = trend[
            "change"
        ]

        confidence = trend[
            "confidence"
        ]

        if change is None:

            change_text = "—"

        else:

            change_text = (
                f"{change:+.2f}%"
            )

        cards += f"""
        <section class="district">

            <h2>{html_escape(district)}</h2>

            <div class="grid">

                <div class="card">
                    <div class="label">
                        有效交易
                    </div>
                    <div class="value">
                        {stats['count']:,} 筆
                    </div>
                </div>

                <div class="card">
                    <div class="label">
                        平均單價
                    </div>
                    <div class="value">
                        {money(stats['average_price'])}
                    </div>
                    <div class="unit">
                        萬元／坪
                    </div>
                </div>

                <div class="card">
                    <div class="label">
                        中位數
                    </div>
                    <div class="value">
                        {money(stats['median_price'])}
                    </div>
                    <div class="unit">
                        萬元／坪
                    </div>
                </div>

                <div class="card">
                    <div class="label">
                        主流平均
                    </div>
                    <div class="value">
                        {money(stats['normal_average'])}
                    </div>
                    <div class="unit">
                        萬元／坪
                    </div>
                </div>

            </div>

            <div class="trend">

                <h3>📈 市場趨勢</h3>

                <p>
                    <strong>
                        {html_escape(direction)}
                    </strong>
                </p>

                <p>
                    期間價格變化：
                    <strong>
                        {change_text}
                    </strong>
                </p>

                <p>
                    樣本可信度：
                    <strong>
                        {html_escape(confidence)}
                    </strong>
                </p>

            </div>

            <h3>🔥 市場熱門路段</h3>

            <table>

                <tr>
                    <th>排名</th>
                    <th>路段</th>
                    <th>交易量</th>
                    <th>平均單價</th>
                    <th>熱度</th>
                </tr>
        """

        for index, route in enumerate(
            data["routes"][:10],
            start=1
        ):

            cards += f"""
                <tr>
                    <td>{index}</td>
                    <td>
                        {html_escape(route['route'])}
                    </td>
                    <td>
                        {route['count']} 筆
                    </td>
                    <td>
                        {money(route['average'])}
                    </td>
                    <td>
                        {money(route['heat'])}
                    </td>
                </tr>
            """

        cards += """
            </table>

            <h3>📊 歷史月份</h3>

            <table>

                <tr>
                    <th>月份</th>
                    <th>交易量</th>
                    <th>平均單價</th>
                    <th>中位數</th>
                    <th>月增率</th>
                </tr>
        """

        for month in data["months"]:

            change = month["change"]

            change_text = (
                f"{change:+.2f}%"
                if change is not None
                else "—"
            )

            cards += f"""
                <tr>
                    <td>
                        {month['month']}
                    </td>
                    <td>
                        {month['count']} 筆
                    </td>
                    <td>
                        {money(month['average'])}
                    </td>
                    <td>
                        {money(month['median'])}
                    </td>
                    <td>
                        {change_text}
                    </td>
                </tr>
            """

        cards += """
            </table>

        </section>
        """

    html = f"""
<!DOCTYPE html>

<html lang="zh-Hant">

<head>

<meta charset="utf-8">

<meta name="viewport"
      content="width=device-width,
               initial-scale=1.0">

<title>
士林區／北投區房市每日報告
</title>

<style>

body {{
    font-family:
        Arial,
        "Microsoft JhengHei",
        sans-serif;

    margin: 0;

    background: #f3f6f9;

    color: #1f2937;
}}

header {{
    background:
        linear-gradient(
            135deg,
            #0f172a,
            #1e3a5f
        );

    color: white;

    padding: 35px 20px;

    text-align: center;
}}

header h1 {{
    margin: 0 0 10px 0;
}}

.container {{
    max-width: 1100px;

    margin: 30px auto;

    padding: 0 20px;
}}

.district {{
    background: white;

    padding: 25px;

    margin-bottom: 30px;

    border-radius: 14px;

    box-shadow:
        0 4px 15px
        rgba(0,0,0,0.08);
}}

.grid {{
    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(180px, 1fr)
        );

    gap: 15px;
}}

.card {{
    background: #f8fafc;

    padding: 20px;

    border-radius: 10px;
}}

.label {{
    color: #64748b;

    font-size: 14px;
}}

.value {{
    font-size: 25px;

    font-weight: bold;

    margin-top: 8px;
}}

.unit {{
    font-size: 13px;

    color: #64748b;
}}

.trend {{
    margin: 25px 0;

    padding: 20px;

    background: #eef6ff;

    border-left:
        5px solid #2563eb;

    border-radius: 8px;
}}

table {{
    width: 100%;

    border-collapse:
        collapse;

    margin-bottom: 25px;
}}

th,
td {{
    padding: 10px;

    border-bottom:
        1px solid #e5e7eb;

    text-align: left;
}}

th {{
    background: #f1f5f9;
}}

footer {{
    text-align: center;

    color: #64748b;

    padding: 30px;
}}

@media(max-width:700px) {{

    .district {{
        padding: 15px;
    }}

    table {{
        font-size: 13px;
    }}

}}

</style>

</head>

<body>

<header>

<h1>
🏠 士林區／北投區房市每日監控報告
</h1>

<p>
產生時間：
{html_escape(generated_at)}
</p>

<p>
房價資料截至：
{html_escape(latest_transaction_date)}
</p>

</header>

    <div class="container">

        {summary}

        {cards}

    </div>

<footer>

台北市士林區／北投區房市監控系統<br>

第九階段：每日房市專業報告

</footer>

</body>

</html>
"""

    return html


# ============================================================
# 儲存報告
# ============================================================

def save_reports(report):

    os.makedirs(
        REPORT_DIR,
        exist_ok=True
    )

    today = datetime.now(ZoneInfo("Asia/Taipei")).strftime(
        "%Y-%m-%d"
    )

    json_file = os.path.join(
        REPORT_DIR,
        f"{today}.json"
    )

    html_file = os.path.join(
        REPORT_DIR,
        f"{today}.html"
    )

    latest_file = os.path.join(
        REPORT_DIR,
        "latest.html"
    )

    with open(
        json_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2
        )

    html = create_html(
        report
    )

    with open(
        html_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(html)

    with open(
        latest_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(html)

    print()
    print("=" * 70)
    print("第九階段房市報告完成")
    print("=" * 70)

    print()
    print(
        f"HTML 報告：{html_file}"
    )

    print(
        f"最新報告：{latest_file}"
    )

    print(
        f"JSON 資料：{json_file}"
    )

    print()
    print(
        "可以在 GitHub 的 reports "
        "資料夾查看報告。"
    )

    print("=" * 70)


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "台北市士林區／北投區"
        "每日房市專業報告引擎"
    )

    print("=" * 70)

    records = load_records()

    print()
    print(
        f"有效住宅買賣資料："
        f"{len(records):,} 筆"
    )

    if not records:

        print(
            "沒有可以產生報告的資料。"
        )

        return

    report = build_report_data(
        records
    )

    save_reports(
        report
    )


# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    main()
