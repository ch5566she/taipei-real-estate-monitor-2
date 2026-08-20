# -*- coding: utf-8 -*-

"""
第31階段：每日房市專業報告＋房仲實戰價格決策

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(BASE_DIR, "data", "taipei_transactions.csv")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
LISTING_COMPARISON_FILE = os.path.join(
    BASE_DIR, "data", "listing_comparison.json"
)
PRICING_DECISIONS_FILE = os.path.join(
    BASE_DIR, "data", "pricing_decisions.csv"
)

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


def build_history_chart(months, district):
    """建立單一行政區的歷史平均單價 SVG 趨勢圖。"""
    valid = []
    for item in months:
        average = item.get("average")
        if average is None:
            continue
        try:
            value = float(average)
        except (TypeError, ValueError):
            continue
        valid.append((str(item.get("month", "")), value))

    if not valid:
        return """
        <div class="history-chart">
            <h3>📈 歷史房價趨勢</h3>
            <div class="no-chart-data">目前沒有足夠的歷史月份資料可繪製趨勢圖。</div>
        </div>
        """

    width, height = 1000, 380
    left, right, top, bottom = 75, 35, 45, 75
    values = [v for _, v in valid]
    low, high = min(values), max(values)
    if high == low:
        low -= 1
        high += 1

    plot_width = width - left - right
    plot_height = height - top - bottom
    points, point_html, label_html, grid_html = [], [], [], []

    for index, (month_name, value) in enumerate(valid):
        x = left + plot_width / 2 if len(valid) == 1 else left + plot_width * index / (len(valid) - 1)
        y = top + plot_height - ((value - low) / (high - low)) * plot_height
        points.append(f"{x:.2f},{y:.2f}")
        point_html.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" class="history-point"></circle>')
        point_html.append(f'<text x="{x:.2f}" y="{max(20, y - 14):.2f}" text-anchor="middle" class="history-value">{value:.2f}</text>')
        label_html.append(f'<text x="{x:.2f}" y="{height - 30}" text-anchor="middle" class="history-label">{html_escape(month_name)}</text>')

    for index in range(5):
        ratio = index / 4
        y = top + plot_height * ratio
        value = high - (high - low) * ratio
        grid_html.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}" class="history-grid"></line>')
        grid_html.append(f'<text x="{left-12}" y="{y+4:.2f}" text-anchor="end" class="history-axis-label">{value:.2f}</text>')

    district_text = html_escape(district)
    return f"""
    <div class="history-chart">
        <h3>📈 歷史房價趨勢</h3>
        <div class="chart-subtitle">{district_text}｜平均單價（萬元／坪）</div>
        <div class="history-chart-box">
            <svg class="history-svg" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="{district_text}歷史平均單價趨勢圖">
                {"".join(grid_html)}
                <line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" class="history-axis"></line>
                <line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" class="history-axis"></line>
                <polyline points="{" ".join(points)}" class="history-line" fill="none"></polyline>
                {"".join(point_html)}
                {"".join(label_html)}
            </svg>
        </div>
    </div>
    """



def build_market_comparison(report):
    """建立士林／北投比較分析與房仲市場判讀。"""
    districts = report.get("districts", {})
    names = [name for name in TARGET_DISTRICTS if name in districts]

    if not names:
        return """
        <section class="market-analysis">
            <h2>📊 士林／北投市場比較分析</h2>
            <div class="analysis-note">目前沒有足夠的行政區資料可進行比較。</div>
        </section>
        """

    rows = ""
    for district in names:
        data = districts[district]
        stats = data.get("stats", {})
        trend = data.get("trend", {})
        change = trend.get("change")
        change_text = "—" if change is None else f"{change:+.2f}%"
        confidence = trend.get("confidence", "低")
        direction = trend.get("direction", "資料不足")
        rows += f"""
            <tr>
                <td><strong>{html_escape(district)}</strong></td>
                <td>{stats.get('count', 0):,} 筆</td>
                <td>{money(stats.get('average_price'))} 萬／坪</td>
                <td>{money(stats.get('median_price'))} 萬／坪</td>
                <td>{html_escape(direction)}</td>
                <td>{change_text}</td>
                <td>{html_escape(confidence)}</td>
            </tr>
        """

    # 比較基準：交易量、平均單價、近期變化
    volume_name = max(names, key=lambda n: districts[n].get("stats", {}).get("count", 0))
    price_name = max(names, key=lambda n: districts[n].get("stats", {}).get("average_price", float("-inf")))

    changes = []
    for district in names:
        change = districts[district].get("trend", {}).get("change")
        if change is not None:
            changes.append((district, float(change)))

    if changes:
        strongest_up = max(changes, key=lambda x: x[1])
        strongest_down = min(changes, key=lambda x: x[1])
    else:
        strongest_up = strongest_down = None

    volume_text = (
        f"{volume_name}目前有效交易量較高，共 {districts[volume_name]['stats'].get('count', 0):,} 筆。"
    )
    price_text = (
        f"{price_name}目前平均單價較高，約 {money(districts[price_name]['stats'].get('average_price'))} 萬／坪。"
    )

    if strongest_down:
        down_name, down_change = strongest_down
        trend_text = f"近期變化以{down_name}較弱，最近3個月約 {down_change:+.2f}%。"
    elif strongest_up:
        up_name, up_change = strongest_up
        trend_text = f"目前有資料的行政區中，{up_name}近期變化相對較強，約 {up_change:+.2f}%。"
    else:
        trend_text = "目前有效月份不足，無法可靠比較近期價格變化。"

    # 房仲行動建議：完全依照目前資料動態生成
    directions = [
        districts[n].get("trend", {}).get("direction")
        for n in names
    ]

    if all(d == "下降" for d in directions if d not in (None, "資料不足")) and any(d == "下降" for d in directions):
        seller_advice = "近期價格偏弱，賣方定價宜以實價與同類型競品為基準，避免明顯高於市場造成銷售週期拉長。"
        buyer_advice = "買方可優先鎖定價格已修正、但地段與產品條件仍佳的物件，並保留合理議價空間。"
    elif any(d == "上升" for d in directions):
        seller_advice = "有上升訊號的行政區可維持貼近市場的價格策略，並用近期成交案例支撐價格。"
        buyer_advice = "買方宜加快對符合需求且價格合理物件的判斷，避免只看單一高價成交而過度追價。"
    else:
        seller_advice = "市場呈現分化或盤整，賣方應依路段、屋齡、產品型態及近期成交個案精準定價。"
        buyer_advice = "買方可採取比價與議價並行策略，重點觀察同路段、同類型物件的實際成交價格。"

    latest_counts = [districts[n].get("trend", {}).get("latest_count", 0) for n in names]
    low_sample = [n for n in names if districts[n].get("trend", {}).get("confidence") == "低"]
    sample_note = ""
    if low_sample:
        sample_note = (
            "；".join(low_sample) +
            "近期樣本可信度偏低，趨勢應搭配路段與住宅類型交叉判讀。"
        )
    else:
        sample_note = "目前各行政區趨勢可作為方向性參考，但仍應搭配路段與產品條件判讀。"

    route_lines = []
    for district in names:
        routes = districts[district].get("routes", [])
        if routes:
            top = routes[0]
            route_name = html_escape(top.get("route", "未命名路段"))
            route_count = top.get("count", 0)
            route_price = money(top.get("average"))
            route_lines.append(
                f"{html_escape(district)}：{route_name}，{route_count} 筆，平均 {route_price} 萬／坪"
            )

    route_html = "".join(f"<li>{line}</li>" for line in route_lines) or "<li>目前沒有足夠路段資料。</li>"

    return f"""
    <section class="market-analysis">
        <h2>📊 士林／北投市場比較分析</h2>

        <table class="comparison-table">
            <tr>
                <th>行政區</th>
                <th>交易量</th>
                <th>平均單價</th>
                <th>中位數</th>
                <th>近期方向</th>
                <th>近3月變化</th>
                <th>可信度</th>
            </tr>
            {rows}
        </table>

        <div class="analysis-grid">
            <div class="analysis-card">
                <div class="analysis-title">📌 交易量比較</div>
                <div>{volume_text}</div>
            </div>
            <div class="analysis-card">
                <div class="analysis-title">💰 價格比較</div>
                <div>{price_text}</div>
            </div>
            <div class="analysis-card">
                <div class="analysis-title">📈 近期變化</div>
                <div>{trend_text}</div>
            </div>
        </div>

        <div class="judgment-box">
            <h3>🤖 房仲市場判讀</h3>
            <p><strong>整體判讀：</strong>{volume_text}{price_text}{trend_text}</p>
            <p><strong>賣方策略：</strong>{seller_advice}</p>
            <p><strong>買方策略：</strong>{buyer_advice}</p>
            <p><strong>開發重點：</strong>優先追蹤交易量較高的行政區與熱門路段，並針對近期價格修正明顯、但交易仍活躍的產品建立待開發名單。</p>
            <p class="analysis-note">⚠️ {html_escape(sample_note)}</p>
        </div>

        <div class="hot-route-box">
            <h3>🔥 各區目前最活躍路段</h3>
            <ul>{route_html}</ul>
        </div>
    </section>
    """

def load_listing_comparison():
    """讀取第20階段「在售物件 × 實價成交比價」結果。"""
    path = LISTING_COMPARISON_FILE
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def format_percent(value):
    if value is None:
        return "—"
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def format_number(value, digits=2):
    if value is None:
        return "—"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def market_badge(market):
    market = market or {}
    level = html_escape(market.get("level", "無法判斷"))
    emoji = html_escape(market.get("emoji", "⚪"))
    description = html_escape(market.get("description", ""))
    return f"""
        <div class="listing-market-badge">
            <strong>{emoji} {level}</strong>
            <span>{description}</span>
        </div>
    """


def build_listing_comparison_section():
    """第22階段：把第20階段 JSON 整合進每日 HTML 報告。"""
    data = load_listing_comparison()

    if not data:
        return """
        <section class="listing-comparison">
            <h2>🏷️ 在售物件 × 實價成交比價決策板</h2>
            <div class="listing-empty">
                目前尚未找到 data/listing_comparison.json。
                請先執行第20階段在售物件 × 實價成交比價引擎。
            </div>
        </section>
        """

    summary = data.get("summary", {}) or {}
    results = data.get("results", []) or []

    generated_at = data.get("generated_at")
    generated_text = "—"
    if generated_at:
        try:
            generated_dt = datetime.fromisoformat(str(generated_at))
            generated_dt = generated_dt.astimezone(ZoneInfo("Asia/Taipei"))
            generated_text = generated_dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            generated_text = str(generated_at)

    summary_cards = f"""
        <div class="listing-summary-grid">
            <div class="listing-summary-card">
                <div class="listing-summary-label">在售物件</div>
                <div class="listing-summary-value">{summary.get("listing_count", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card">
                <div class="listing-summary-label">成交比較資料</div>
                <div class="listing-summary-value">{summary.get("transaction_count", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card listing-good">
                <div class="listing-summary-label">低於市場</div>
                <div class="listing-summary-value">{summary.get("below_market", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card">
                <div class="listing-summary-label">接近／合理偏高</div>
                <div class="listing-summary-value">{summary.get("near_market", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card listing-warning">
                <div class="listing-summary-label">高於市場</div>
                <div class="listing-summary-value">{summary.get("above_market", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
            <div class="listing-summary-card">
                <div class="listing-summary-label">樣本不足</div>
                <div class="listing-summary-value">{summary.get("insufficient_sample", 0):,}</div>
                <div class="listing-summary-unit">筆</div>
            </div>
        </div>
        <div class="listing-meta">
            比價資料產生時間（台灣時間）：{html_escape(generated_text)}
        </div>
    """

    item_blocks = []

    for index, result in enumerate(results, start=1):
        listing = result.get("listing", {}) or {}
        comparison = result.get("comparison", {}) or {}
        market = comparison.get("market", {}) or {}
        recommendations = comparison.get("recommendations", {}) or {}
        comparables = comparison.get("comparables", []) or []

        listing_id = listing.get("listing_id") or f"物件 {index}"
        district = listing.get("district", "")
        title = listing.get("title") or "未命名在售物件"
        location = listing.get("location") or listing.get("street") or "未提供位置"

        comparable_rows = ""
        for comp_index, comparable in enumerate(comparables, start=1):
            comparable_rows += f"""
                <tr>
                    <td>{comp_index}</td>
                    <td>{html_escape(comparable.get("date") or "—")}</td>
                    <td>{html_escape(comparable.get("street") or comparable.get("location") or "—")}</td>
                    <td>{format_number(comparable.get("area"))}</td>
                    <td><strong>{format_number(comparable.get("unit_price"))}</strong></td>
                    <td>{format_number(comparable.get("transaction_price"))}</td>
                    <td>{html_escape(comparable.get("building_type") or "—")}</td>
                    <td>{format_number(comparable.get("score"), 0)}</td>
                </tr>
            """

        if not comparable_rows:
            comparable_rows = """
                <tr>
                    <td colspan="8" class="listing-no-data">沒有可顯示的成交比較案例。</td>
                </tr>
            """

        item_blocks.append(f"""
            <article class="listing-item">
                <div class="listing-item-header">
                    <div>
                        <div class="listing-item-number">物件 #{index}</div>
                        <h3>{html_escape(title)}</h3>
                        <div class="listing-location">
                            {html_escape(district)}｜{html_escape(location)}
                        </div>
                    </div>
                    {market_badge(market)}
                </div>

                <div class="listing-facts">
                    <div>
                        <span>建物坪數</span>
                        <strong>{format_number(listing.get("building_area"))} 坪</strong>
                    </div>
                    <div>
                        <span>目前開價單價</span>
                        <strong>{format_number(listing.get("unit_price"))} 萬／坪</strong>
                    </div>
                    <div>
                        <span>目前總價</span>
                        <strong>{format_number(listing.get("total_price"))} 萬</strong>
                    </div>
                    <div>
                        <span>比較樣本</span>
                        <strong>{comparison.get("sample_count", 0):,} 筆</strong>
                    </div>
                </div>

                <div class="listing-comparison-grid">
                    <div class="listing-analysis-card">
                        <h4>📊 成交市場基準</h4>
                        <p>市場平均：<strong>{format_number(comparison.get("market_average"))} 萬／坪</strong></p>
                        <p>市場中位數：<strong>{format_number(comparison.get("market_median"))} 萬／坪</strong></p>
                        <p>Q1：<strong>{format_number(comparison.get("q1"))} 萬／坪</strong></p>
                        <p>Q3：<strong>{format_number(comparison.get("q3"))} 萬／坪</strong></p>
                        <p>開價溢／折價：<strong>{format_percent(comparison.get("premium_percent"))}</strong></p>
                    </div>

                    <div class="listing-analysis-card">
                        <h4>💰 房仲議價決策</h4>
                        <p>買方建議價：
                            <strong>{format_number(recommendations.get("buyer_price_low"))}
                            ～ {format_number(recommendations.get("buyer_price_high"))} 萬／坪</strong>
                        </p>
                        <p>賣方市場價格帶：
                            <strong>{format_number(recommendations.get("seller_price_low"))}
                            ～ {format_number(recommendations.get("seller_price_high"))} 萬／坪</strong>
                        </p>
                        <p class="listing-note">
                            ⚠️ {html_escape(recommendations.get("note") or "—")}
                        </p>
                    </div>
                </div>

                <h4 class="listing-comparable-title">🔎 主要實價比較案例</h4>
                <div class="listing-table-wrap">
                    <table class="listing-comparable-table">
                        <tr>
                            <th>#</th>
                            <th>成交日期</th>
                            <th>路段／位置</th>
                            <th>坪數</th>
                            <th>單價</th>
                            <th>總價</th>
                            <th>建物類型</th>
                            <th>匹配分數</th>
                        </tr>
                        {comparable_rows}
                    </table>
                </div>

                <div class="listing-id">物件編號：{html_escape(listing_id)}</div>
            </article>
        """)

    item_html = "".join(item_blocks) if item_blocks else """
        <div class="listing-empty">
            比價 JSON 已成功讀取，但目前沒有在售物件分析結果。
        </div>
    """

    return f"""
    <section class="listing-comparison">
        <div class="listing-section-title">
            <div>
                <h2>🏷️ 在售物件 × 實價成交比價決策板</h2>
                <p>
                    將目前在售開價與實價成交案例放在同一張決策板，
                    協助快速判斷開價位置、買方可談區間與賣方合理價格帶。
                </p>
            </div>
        </div>

        {summary_cards}

        <div class="listing-method-note">
            <strong>比價邏輯：</strong>
            本區直接使用第20階段產生的
            <code>data/listing_comparison.json</code>，
            不重新計算成交案例，確保與獨立比價引擎一致。
        </div>

        {item_html}
    </section>
    """



# ============================================================
# 第31階段：房仲實戰價格決策儀表板
# ============================================================

def load_pricing_decisions():
    """讀取 pricing_engine.py 產生的 data/pricing_decisions.csv。

    本區只負責展示決策引擎結果，不重新計算成交案例，避免報告頁與
    第29/30階段的價格決策結果產生不一致。
    """
    path = PRICING_DECISIONS_FILE
    if not os.path.exists(path):
        return []

    rows = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if not isinstance(row, dict):
                    continue
                rows.append(row)
    except (OSError, csv.Error):
        return []
    return rows


def pricing_value(row, key):
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text.replace(",", ""))
    except (TypeError, ValueError):
        return None


def pricing_int(row, key):
    value = pricing_value(row, key)
    if value is None:
        return 0
    return int(round(value))


def pricing_text(row, key, default="—"):
    value = row.get(key)
    if value is None or str(value).strip() == "":
        return default
    return html_escape(value)


def pricing_grade_class(grade):
    grade = str(grade or "").strip()
    if grade in ("價格偏低", "低於市場"):
        return "pricing-good"
    if grade in ("接近市場", "合理偏高", "接近／合理偏高"):
        return "pricing-neutral"
    if grade in ("偏高", "價格過高", "高於市場"):
        return "pricing-high"
    return "pricing-insufficient"


def build_pricing_decision_section():
    """把第29/30階段 pricing_decisions.csv 整合進每日報告。"""
    rows = load_pricing_decisions()

    if not rows:
        return """
        <section class="pricing-decision">
            <div class="pricing-section-title">
                <h2>💰 房仲實戰價格決策儀表板</h2>
                <p>尚未找到 data/pricing_decisions.csv。請先執行房仲實戰價格決策引擎。</p>
            </div>
        </section>
        """

    # 價格等級統計；兼容舊版與新版文字。
    counts = {
        "低於市場": 0,
        "接近市場": 0,
        "高於市場": 0,
        "樣本不足": 0,
    }
    grade_alias = {
        "價格偏低": "低於市場",
        "價格過高": "高於市場",
        "偏高": "高於市場",
        "合理偏高": "接近市場",
        "接近／合理偏高": "接近市場",
    }
    for row in rows:
        raw = str(row.get("price_grade") or "樣本不足").strip()
        bucket = grade_alias.get(raw, raw)
        if bucket not in counts:
            bucket = "樣本不足"
        counts[bucket] += 1

    total = len(rows)
    cards = f"""
        <div class="pricing-summary-grid">
            <div class="pricing-summary-card">
                <div class="pricing-summary-label">分析物件</div>
                <div class="pricing-summary-value">{total:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-good">
                <div class="pricing-summary-label">低於市場</div>
                <div class="pricing-summary-value">{counts['低於市場']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-neutral">
                <div class="pricing-summary-label">接近市場</div>
                <div class="pricing-summary-value">{counts['接近市場']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-high">
                <div class="pricing-summary-label">高於市場</div>
                <div class="pricing-summary-value">{counts['高於市場']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
            <div class="pricing-summary-card pricing-insufficient">
                <div class="pricing-summary-label">樣本不足</div>
                <div class="pricing-summary-value">{counts['樣本不足']:,}</div>
                <div class="pricing-summary-unit">筆</div>
            </div>
        </div>
        <div class="pricing-method-note">
            <strong>決策來源：</strong>直接讀取 <code>data/pricing_decisions.csv</code>，
            顯示第29/30階段價格決策引擎的結果；本頁不重新計算成交案例。
        </div>
    """

    item_blocks = []
    for index, row in enumerate(rows, start=1):
        grade = str(row.get("price_grade") or "樣本不足").strip()
        grade_class = pricing_grade_class(grade)
        confidence = str(row.get("confidence") or "低").strip()
        summary = row.get("comparable_grade_summary") or (
            f"A{pricing_int(row, 'grade_a_count')}/"
            f"B{pricing_int(row, 'grade_b_count')}/"
            f"C{pricing_int(row, 'grade_c_count')}"
        )
        current_unit = pricing_value(row, "current_unit_price")
        weighted_unit = pricing_value(row, "weighted_market_unit_price")
        median_unit = pricing_value(row, "median_transaction_unit_price")
        gap = pricing_value(row, "price_gap_percent")
        low_price = pricing_value(row, "reasonable_low_price")
        high_price = pricing_value(row, "reasonable_high_price")
        buyer_first = pricing_value(row, "buyer_first_price")
        buyer_max = pricing_value(row, "buyer_max_price")
        seller_price = pricing_value(row, "seller_reasonable_price")
        negotiation = pricing_value(row, "negotiation_percent")

        if grade == "樣本不足":
            action = "先補足同類型成交樣本，再做正式議價判斷。"
        elif grade in ("價格過高", "偏高", "高於市場"):
            action = "列入議價重點；先確認屋況、樓層、車位與裝潢差異，再以成交基準回推合理價格。"
        elif grade in ("價格偏低", "低於市場"):
            action = "價格具有吸引力，但仍應檢查是否存在特殊瑕疵、權利或產品差異。"
        else:
            action = "價格接近市場，可把重點放在產品優缺點、付款條件與議價空間。"

        comparable_info = f"""
            <div class="pricing-comparable-meta">
                <span>A級 {pricing_int(row, 'grade_a_count')} 筆</span>
                <span>B級 {pricing_int(row, 'grade_b_count')} 筆</span>
                <span>C級 {pricing_int(row, 'grade_c_count')} 筆</span>
                <span>核心 {pricing_int(row, 'core_comparable_count')} 筆</span>
                <span>排除 {pricing_int(row, 'excluded_count')} 筆</span>
            </div>
        """

        item_blocks.append(f"""
            <article class="pricing-item">
                <div class="pricing-item-header">
                    <div>
                        <div class="pricing-item-number">物件 #{index}｜{pricing_text(row, 'listing_id')}</div>
                        <h3>{pricing_text(row, 'title', '未命名在售物件')}</h3>
                        <div class="pricing-location">
                            {pricing_text(row, 'district', '')}｜{pricing_text(row, 'location', '未提供位置')}
                        </div>
                    </div>
                    <div class="pricing-badge {grade_class}">
                        <strong>{html_escape(grade)}</strong>
                        <span>信心：{html_escape(confidence)}</span>
                    </div>
                </div>

                <div class="pricing-facts">
                    <div><span>目前開價</span><strong>{money(pricing_value(row, 'current_price'))} 萬</strong></div>
                    <div><span>目前開價單價</span><strong>{money(current_unit)} 萬／坪</strong></div>
                    <div><span>加權市場單價</span><strong>{money(weighted_unit)} 萬／坪</strong></div>
                    <div><span>價格差距</span><strong>{format_percent(gap)}</strong></div>
                </div>

                <div class="pricing-decision-grid">
                    <div class="pricing-analysis-card">
                        <h4>📊 市場基準</h4>
                        <p>加權市場單價：<strong>{money(weighted_unit)} 萬／坪</strong></p>
                        <p>成交中位單價：<strong>{money(median_unit)} 萬／坪</strong></p>
                        <p>比較樣本：<strong>{pricing_int(row, 'comparable_count')} 筆</strong></p>
                        <p>案例品質：<strong>{html_escape(summary)}</strong></p>
                        {comparable_info}
                    </div>
                    <div class="pricing-analysis-card pricing-action-card">
                        <h4>💰 房仲議價決策</h4>
                        <p>合理價格：<strong>{money(low_price)} ～ {money(high_price)} 萬</strong></p>
                        <p>買方第一口：<strong>{money(buyer_first)} 萬</strong></p>
                        <p>買方最高價：<strong>{money(buyer_max)} 萬</strong></p>
                        <p>賣方合理價：<strong>{money(seller_price)} 萬</strong></p>
                        <p>理論議價幅度：<strong>{format_percent(negotiation)}</strong></p>
                    </div>
                </div>

                <div class="pricing-action-note">
                    <strong>🎯 實戰建議：</strong>{html_escape(action)}
                </div>
                <div class="pricing-safety-note">
                    ⚠️ 本區間屬資料模型的決策輔助，不代表保證成交價；樣本不足時不得把空白價格區間解讀成零元或無議價空間。
                </div>
            </article>
        """)

    return f"""
    <section class="pricing-decision">
        <div class="pricing-section-title">
            <h2>💰 房仲實戰價格決策儀表板</h2>
            <p>把「目前在售開價」與「實價成交模型」轉成可直接拿來談案、估價、議價的決策資訊。</p>
        </div>
        {cards}
        {''.join(item_blocks)}
    </section>
    """


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
    market_analysis = build_market_comparison(report)
    listing_comparison_html = build_listing_comparison_section()
    pricing_decision_html = build_pricing_decision_section()

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
        if isinstance(latest_transaction_date, (tuple, list)):
            if len(latest_transaction_date) >= 3:
                latest_transaction_date = (
                    f"{latest_transaction_date[0]}年"
                    f"{latest_transaction_date[1]}月"
                    f"{latest_transaction_date[2]}日"
                )
            else:
                latest_transaction_date = str(latest_transaction_date)
        elif hasattr(latest_transaction_date, "strftime"):
            latest_transaction_date = latest_transaction_date.strftime("%Y年%m月%d日")
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
        """

        cards += build_history_chart(
            data["months"],
            district,
        )

        cards += """
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

.market-analysis {{
    margin: 25px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.market-analysis h2 {{
    margin-top: 0;
}}

.market-analysis h3 {{
    margin-top: 0;
}}

.comparison-table {{
    margin-bottom: 18px;
}}

.analysis-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 18px 0;
}}

.analysis-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.8;
}}

.analysis-title {{
    color: #1d4ed8;
    font-weight: 700;
    margin-bottom: 6px;
}}

.judgment-box {{
    margin-top: 18px;
    padding: 20px;
    background: #eef6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.9;
}}

.judgment-box p {{
    margin: 8px 0;
}}

.analysis-note {{
    color: #64748b;
    font-size: 13px;
}}

.hot-route-box {{
    margin-top: 18px;
    padding: 18px;
    background: #fff7ed;
    border-left: 5px solid #f97316;
    border-radius: 10px;
}}

.hot-route-box ul {{
    margin: 8px 0 0 20px;
    padding: 0;
}}

.history-chart {{
    display: block;
    width: 100%;
    margin: 28px 0 10px 0;
}}

.history-chart h3 {{ margin: 0 0 8px 0; }}
.chart-subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 10px; }}
.history-chart-box {{ display: block; width: 100%; overflow-x: auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 10px; box-sizing: border-box; }}
.history-svg {{ display: block; width: 100%; min-width: 760px; height: auto; }}
.history-grid {{ stroke: #e2e8f0; stroke-width: 1; }}
.history-axis {{ stroke: #94a3b8; stroke-width: 1.2; }}
.history-line {{ stroke: #2563eb; stroke-width: 4; stroke-linejoin: round; stroke-linecap: round; }}
.history-point {{ fill: #ffffff; stroke: #2563eb; stroke-width: 3; }}
.history-label {{ fill: #475569; font-size: 12px; }}
.history-axis-label {{ fill: #64748b; font-size: 11px; }}
.history-value {{ fill: #1d4ed8; font-size: 11px; font-weight: bold; }}
.no-chart-data {{ background: #f8fafc; color: #64748b; padding: 18px; border-radius: 10px; text-align: center; }}


.listing-comparison {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.listing-section-title h2 {{ margin: 0 0 8px 0; }}
.listing-section-title p {{ margin: 0 0 18px 0; color: #64748b; line-height: 1.8; }}

.listing-summary-grid {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 10px;
    margin: 18px 0;
}}

.listing-summary-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px;
}}

.listing-summary-card.listing-good {{ background: #f0fdf4; border-color: #bbf7d0; }}
.listing-summary-card.listing-warning {{ background: #fff7ed; border-color: #fed7aa; }}
.listing-summary-label {{ color: #64748b; font-size: 13px; }}
.listing-summary-value {{ margin-top: 5px; font-size: 23px; font-weight: 700; }}
.listing-summary-unit {{ color: #64748b; font-size: 12px; }}
.listing-meta {{ color: #64748b; font-size: 12px; margin: 4px 0 18px 0; }}

.listing-method-note {{
    margin: 16px 0 20px 0;
    padding: 14px 16px;
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    color: #475569;
    line-height: 1.7;
}}

.listing-method-note code {{
    background: #e2e8f0;
    padding: 2px 5px;
    border-radius: 4px;
}}

.listing-item {{
    margin-top: 22px;
    padding: 20px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background: #ffffff;
}}

.listing-item-header {{
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: flex-start;
}}

.listing-item-number {{ color: #2563eb; font-size: 12px; font-weight: 700; margin-bottom: 4px; }}
.listing-item-header h3 {{ margin: 0 0 6px 0; }}
.listing-location {{ color: #64748b; font-size: 13px; }}

.listing-market-badge {{
    min-width: 180px;
    padding: 12px 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}}

.listing-market-badge strong {{ display: block; margin-bottom: 4px; }}
.listing-market-badge span {{ display: block; color: #64748b; font-size: 12px; line-height: 1.5; }}

.listing-facts {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 18px 0;
}}

.listing-facts > div {{ padding: 12px; background: #f8fafc; border-radius: 8px; }}
.listing-facts span {{ display: block; color: #64748b; font-size: 12px; margin-bottom: 5px; }}
.listing-facts strong {{ font-size: 17px; }}

.listing-comparison-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin: 16px 0;
}}

.listing-analysis-card {{
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    line-height: 1.7;
}}

.listing-analysis-card h4 {{ margin: 0 0 8px 0; }}
.listing-analysis-card p {{ margin: 5px 0; }}
.listing-note {{ color: #64748b; font-size: 13px; }}
.listing-comparable-title {{ margin: 20px 0 10px 0; }}
.listing-table-wrap {{ width: 100%; overflow-x: auto; }}
.listing-comparable-table {{ min-width: 850px; }}
.listing-comparable-table th, .listing-comparable-table td {{ white-space: nowrap; }}
.listing-no-data {{ text-align: center; color: #64748b; padding: 18px; }}
.listing-id {{ margin-top: 10px; color: #94a3b8; font-size: 11px; }}

.listing-empty {{
    padding: 18px;
    background: #f8fafc;
    color: #64748b;
    border-radius: 10px;
    line-height: 1.7;
}}



.pricing-decision {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.pricing-section-title h2 {{ margin: 0 0 8px 0; }}
.pricing-section-title p {{ margin: 0 0 18px 0; color: #64748b; line-height: 1.8; }}

.pricing-summary-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
    margin: 18px 0;
}}

.pricing-summary-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 14px;
}}
.pricing-summary-card.pricing-good {{ background: #f0fdf4; border-color: #bbf7d0; }}
.pricing-summary-card.pricing-neutral {{ background: #eff6ff; border-color: #bfdbfe; }}
.pricing-summary-card.pricing-high {{ background: #fff7ed; border-color: #fed7aa; }}
.pricing-summary-card.pricing-insufficient {{ background: #f8fafc; border-color: #cbd5e1; }}
.pricing-summary-label {{ color: #64748b; font-size: 13px; }}
.pricing-summary-value {{ margin-top: 5px; font-size: 23px; font-weight: 700; }}
.pricing-summary-unit {{ color: #64748b; font-size: 12px; }}

.pricing-method-note {{
    margin: 16px 0 20px 0;
    padding: 14px 16px;
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    color: #475569;
    line-height: 1.7;
}}
.pricing-method-note code {{ background: #e2e8f0; padding: 2px 5px; border-radius: 4px; }}

.pricing-item {{
    margin-top: 22px;
    padding: 20px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background: #ffffff;
}}
.pricing-item-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }}
.pricing-item-number {{ color: #2563eb; font-size: 12px; font-weight: 700; margin-bottom: 4px; }}
.pricing-item-header h3 {{ margin: 0 0 6px 0; }}
.pricing-location {{ color: #64748b; font-size: 13px; }}

.pricing-badge {{
    min-width: 150px;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
    background: #f8fafc;
}}
.pricing-badge strong {{ display: block; margin-bottom: 4px; }}
.pricing-badge span {{ display: block; color: #64748b; font-size: 12px; }}
.pricing-badge.pricing-good {{ background: #f0fdf4; border-color: #86efac; }}
.pricing-badge.pricing-neutral {{ background: #eff6ff; border-color: #93c5fd; }}
.pricing-badge.pricing-high {{ background: #fff7ed; border-color: #fdba74; }}
.pricing-badge.pricing-insufficient {{ background: #f8fafc; border-color: #cbd5e1; }}

.pricing-facts {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 18px 0;
}}
.pricing-facts > div {{ padding: 12px; background: #f8fafc; border-radius: 8px; }}
.pricing-facts span {{ display: block; color: #64748b; font-size: 12px; margin-bottom: 5px; }}
.pricing-facts strong {{ font-size: 17px; }}

.pricing-decision-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin: 16px 0;
}}
.pricing-analysis-card {{
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    line-height: 1.7;
}}
.pricing-analysis-card h4 {{ margin: 0 0 8px 0; }}
.pricing-analysis-card p {{ margin: 5px 0; }}
.pricing-action-card {{ background: #f0fdf4; border-color: #bbf7d0; }}
.pricing-comparable-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
.pricing-comparable-meta span {{ background: #e2e8f0; padding: 3px 7px; border-radius: 999px; font-size: 11px; color: #475569; }}
.pricing-action-note {{ margin-top: 14px; padding: 14px 16px; background: #eff6ff; border-left: 4px solid #2563eb; border-radius: 8px; line-height: 1.8; }}
.pricing-safety-note {{ margin-top: 10px; color: #64748b; font-size: 12px; line-height: 1.7; }}

@media(max-width:700px) {{

    .district {{
        padding: 15px;
    }}

    table {{
        font-size: 13px;
    }}

    .listing-summary-grid {{
        grid-template-columns: repeat(2, 1fr);
    }}

    .listing-item-header {{
        display: block;
    }}

    .listing-market-badge {{
        margin-top: 12px;
        min-width: 0;
    }}

    .listing-facts {{
        grid-template-columns: repeat(2, 1fr);
    }}

    .listing-comparison-grid {{
        grid-template-columns: 1fr;
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

        {market_analysis}

        {listing_comparison_html}

        {pricing_decision_html}

        {cards}

    </div>

<footer>

台北市士林區／北投區房市監控系統<br>

第十階段：每日房市專業報告＋市場判讀

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
    print("第31階段房市報告完成")
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
