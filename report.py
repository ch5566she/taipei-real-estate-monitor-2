# -*- coding: utf-8 -*-

"""
第十二階段：房市異常警報＋房仲開發名單

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
# 第12階段：路段異常監控＋房仲開發名單
# ============================================================

def route_monitor_analysis(items, district_stats):
    """
    路段級異常監控：
    1. 最新月份價格變化
    2. 最新月份交易量變化
    3. 路段平均價與行政區中位數的差距
    4. 房仲開發分數

    注意：
    - 僅使用實際有交易的月份。
    - 至少需要兩個月份才計算路段價格變化。
    - 樣本不足時不產生強烈的異常判斷。
    """
    groups = {}

    for item in items:
        route = item.get("route") or "未知路段"
        date_value = item.get("date")
        if not date_value:
            continue

        groups.setdefault(route, []).append(item)

    district_median = district_stats.get("median_price")

    district_dates = [
        item.get("date")
        for item in items
        if item.get("date")
    ]
    district_latest_key = (
        max((d[0], d[1]) for d in district_dates)
        if district_dates
        else None
    )

    result = []

    for route, group in groups.items():
        if len(group) < 2:
            continue

        month_groups = {}

        for item in group:
            date_value = item.get("date")
            if not date_value:
                continue

            year, month, _ = date_value
            key = (year, month)

            month_groups.setdefault(key, []).append(
                item.get("unit_price")
            )

        month_rows = []
        for (year, month), prices in sorted(month_groups.items()):
            prices = [
                float(p) for p in prices
                if p is not None
            ]
            if not prices:
                continue

            month_rows.append({
                "month": f"{year:04d}-{month:02d}",
                "count": len(prices),
                "average": mean(prices),
            })

        latest = month_rows[-1] if month_rows else None
        previous = month_rows[-2] if len(month_rows) >= 2 else None

        price_change = None
        if latest and previous and previous["average"]:
            price_change = (
                (latest["average"] - previous["average"])
                / previous["average"]
                * 100
            )

        volume_change = None
        if latest and previous and previous["count"]:
            volume_change = (
                (latest["count"] - previous["count"])
                / previous["count"]
                * 100
            )

        route_age_months = None
        if latest and district_latest_key:
            try:
                route_year, route_month = (
                    int(latest["month"][:4]),
                    int(latest["month"][5:7])
                )
                district_year, district_month = district_latest_key
                route_age_months = (
                    (district_year - route_year) * 12
                    + (district_month - route_month)
                )
            except (TypeError, ValueError):
                route_age_months = None

        average_price = mean(
            float(item["unit_price"])
            for item in group
            if item.get("unit_price") is not None
        )

        price_gap = None
        if district_median:
            price_gap = (
                (average_price - district_median)
                / district_median
                * 100
            )

        # 開發分數（100分）：
        # 交易量 30 + 熱度/價格 20 + 最新交易量 20
        # + 資料新鮮度 20 + 異常訊號 10
        count_score = min(len(group) / 10, 1.0) * 30

        heat_score = min(
            (len(group) * average_price) / 1200,
            1.0
        ) * 20

        latest_score = min(
            (latest["count"] if latest else 0) / 5,
            1.0
        ) * 20

        if route_age_months is None:
            recency_score = 0
        elif route_age_months <= 1:
            recency_score = 20
        elif route_age_months <= 3:
            recency_score = 16
        elif route_age_months <= 6:
            recency_score = 11
        elif route_age_months <= 12:
            recency_score = 6
        else:
            recency_score = 0

        signal_score = 0
        if price_change is not None and price_change <= -10:
            signal_score += 10
        elif price_change is not None and price_change >= 10:
            signal_score += 7

        development_score = round(
            count_score
            + heat_score
            + latest_score
            + recency_score
            + signal_score,
            1
        )

        result.append({
            "route": route,
            "count": len(group),
            "average": average_price,
            "latest_month": latest["month"] if latest else None,
            "latest_count": latest["count"] if latest else 0,
            "latest_average": latest["average"] if latest else None,
            "previous_month": previous["month"] if previous else None,
            "previous_count": previous["count"] if previous else 0,
            "previous_average": previous["average"] if previous else None,
            "price_change": price_change,
            "volume_change": volume_change,
            "route_age_months": route_age_months,
            "price_gap_vs_district_median": price_gap,
            "development_score": development_score,
        })

    result.sort(
        key=lambda x: x["development_score"],
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

        trend_windows = build_trend_windows(
            months
        )

        price_bands = build_price_bands(
            items
        )

        routes = route_analysis(
            items
        )

        route_monitor = route_monitor_analysis(
            items,
            stats
        )

        report["districts"][
            district
        ] = {

            "stats": stats,

            "trend": trend,

            "months": months,

            "trend_windows": trend_windows,

            "price_bands": price_bands,

            "routes": routes,
            "route_monitor": route_monitor,
            "latest_transaction_date": max(
                (item.get("date") for item in items if item.get("date")),
                default=None
            ),
            }

    # 第14階段：把市場機會排序一併寫入 JSON，
    # 方便未來接 API、LINE、Email 或其他儀表板。
    report["opportunity"] = build_opportunity_data(report)

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




def calculate_window_change(months, window):
    """
    計算最近 N 個「有資料月份」的價格變化。
    以第一個月份與最新月份的平均單價比較。
    注意：月份可能不連續，因此標示為「最近N個有資料月份」。
    """
    valid = [
        item for item in (months or [])
        if item.get("average") is not None
    ]

    if len(valid) < 2:
        return None

    recent = valid[-window:] if len(valid) >= window else valid

    first = to_float(recent[0].get("average"))
    latest = to_float(recent[-1].get("average"))

    if first in (None, 0) or latest is None:
        return None

    return (latest - first) / first * 100


def get_recent_month_info(months, window=3):
    """取得最近 N 個有資料月份的摘要。"""
    valid = [
        item for item in (months or [])
        if item.get("average") is not None
    ]

    if not valid:
        return {
            "count": 0,
            "start_month": None,
            "end_month": None,
            "change": None,
            "latest_average": None,
            "latest_count": 0,
        }

    recent = valid[-window:]
    latest = recent[-1]

    return {
        "count": len(recent),
        "start_month": recent[0].get("month"),
        "end_month": latest.get("month"),
        "change": calculate_window_change(valid, window),
        "latest_average": latest.get("average"),
        "latest_count": latest.get("count", 0),
    }



# ============================================================
# 第13階段：多期間趨勢＋價格帶分析
# ============================================================

PRICE_BANDS = [
    ("50萬以下", None, 50),
    ("50–70萬", 50, 70),
    ("70–90萬", 70, 90),
    ("90–110萬", 90, 110),
    ("110萬以上", 110, None),
]


def build_trend_windows(months):
    """
    計算最近 3／6／12 個「有資料月份」的價格變化。
    注意：月份可能不連續，因此明確標示為「有資料月份」。
    """
    result = {}

    for window in (3, 6, 12):
        info = get_recent_month_info(months, window)
        info["window"] = window
        info["label"] = f"近{window}個有資料月份"
        result[str(window)] = info

    return result


def build_price_bands(items):
    """
    依每筆成交單價建立價格帶。
    單價單位沿用本系統的「萬元／坪」。
    """
    total = len(items)
    result = []

    for label, lower, upper in PRICE_BANDS:
        group = []

        for item in items:
            price = to_float(item.get("unit_price"))

            if price is None:
                continue

            if lower is None:
                matched = price < upper
            elif upper is None:
                matched = price >= lower
            else:
                matched = lower <= price < upper

            if matched:
                group.append(item)

        count = len(group)
        share = (count / total * 100) if total else None
        average = (
            mean(item["unit_price"] for item in group)
            if group else None
        )

        result.append({
            "band": label,
            "lower": lower,
            "upper": upper,
            "count": count,
            "share": share,
            "average": average,
        })

    return result


def build_price_band_summary(price_bands):
    """找出交易量最高的價格帶。"""
    valid = [
        item for item in (price_bands or [])
        if item.get("count", 0) > 0
    ]

    if not valid:
        return None

    return max(valid, key=lambda item: item.get("count", 0))


def build_decision_dashboard(report):
    """
    第11階段：房仲實戰決策儀表板。
    所有數字與建議均依當日 report 動態計算。
    """
    districts = report.get("districts", {})
    names = [n for n in TARGET_DISTRICTS if n in districts]

    if not names:
        return """
        <section class="decision-dashboard">
            <h2>🎯 房仲實戰決策儀表板</h2>
            <div class="analysis-note">目前沒有足夠資料產生決策儀表板。</div>
        </section>
        """

    metrics = {}

    for district in names:
        data = districts[district]
        months = data.get("months", [])
        stats = data.get("stats", {})
        trend = data.get("trend", {})

        recent3 = get_recent_month_info(months, 3)
        recent6 = get_recent_month_info(months, 6)
        recent12 = get_recent_month_info(months, 12)
        trend_windows = data.get("trend_windows", {})

        metrics[district] = {
            "count": stats.get("count", 0),
            "average": stats.get("average_price"),
            "median": stats.get("median_price"),
            "trend": trend.get("direction", "資料不足"),
            "trend_change": trend.get("change"),
            "confidence": trend.get("confidence", "低"),
            "recent3": recent3,
            "recent6": recent6,
            "recent12": recent12,
            "trend_windows": trend_windows,
        }

    # --------------------------------------------------------
    # 跨行政區比較
    # --------------------------------------------------------
    volume_rank = sorted(
        names,
        key=lambda n: metrics[n]["count"],
        reverse=True,
    )

    price_rank = sorted(
        names,
        key=lambda n: (
            metrics[n]["average"]
            if metrics[n]["average"] is not None
            else float("-inf")
        ),
        reverse=True,
    )

    recent_change_values = [
        (n, metrics[n]["recent3"]["change"])
        for n in names
        if metrics[n]["recent3"]["change"] is not None
    ]

    if recent_change_values:
        strongest = max(recent_change_values, key=lambda x: x[1])
        weakest = min(recent_change_values, key=lambda x: x[1])
    else:
        strongest = weakest = None

    total_volume = sum(metrics[n]["count"] for n in names)
    volume_text = "；".join(
        f"{n} {metrics[n]['count']:,}筆"
        for n in volume_rank
    )

    if len(names) >= 2:
        a, b = price_rank[0], price_rank[1]
        avga = metrics[a]["average"]
        avgb = metrics[b]["average"]

        if avga is not None and avgb is not None and avgb != 0:
            gap_pct = (avga - avgb) / avgb * 100
            price_gap_text = (
                f"{a}平均單價較{b}高 "
                f"{gap_pct:+.2f}%。"
            )
        else:
            price_gap_text = "兩區平均單價資料不足，暫無法比較。"
    else:
        price_gap_text = "目前只有一個行政區有資料。"

    # --------------------------------------------------------
    # 警示
    # --------------------------------------------------------
    alerts = []

    for district in names:
        m = metrics[district]
        change3 = m["recent3"]["change"]
        latest_count = m["recent3"]["latest_count"]

        if change3 is not None and change3 <= -10:
            alerts.append(
                f"🔴 {district}最近3個有資料月份價格下跌 "
                f"{abs(change3):.2f}%，應提高議價與定價風險注意。"
            )
        elif change3 is not None and change3 >= 10:
            alerts.append(
                f"🟢 {district}最近3個有資料月份價格上升 "
                f"{change3:.2f}%，可留意高需求產品的價格支撐。"
            )

        if latest_count < 3:
            alerts.append(
                f"⚠️ {district}最新月份僅 {latest_count} 筆，"
                "近期價格訊號可信度偏低。"
            )

    if not alerts:
        alerts.append(
            "🟡 目前沒有觸發明顯價格異常警示，仍應搭配路段與產品類型判讀。"
        )

    # --------------------------------------------------------
    # 房仲實戰建議
    # --------------------------------------------------------
    if strongest and strongest[1] >= 5:
        seller_advice = (
            f"{strongest[0]}近期價格相對有支撐，可優先整理近期成交案例，"
            "協助屋主建立合理售價區間。"
        )
    elif weakest and weakest[1] <= -5:
        seller_advice = (
            f"{weakest[0]}近期價格修正較明顯，賣方開價應更貼近實價，"
            "並預留合理議價空間，以降低銷售週期。"
        )
    else:
        seller_advice = (
            "目前兩區沒有形成明顯單邊價格訊號，賣方應採「同路段、"
            "同屋齡、同產品」三項條件比價後定價。"
        )

    if weakest and weakest[1] <= -5:
        buyer_advice = (
            f"買方可優先關注{weakest[0]}近期價格修正的物件，"
            "但要排除低總價、特殊屋況或非主流產品造成的價格偏差。"
        )
    else:
        buyer_advice = (
            "買方宜以近期成交與同路段產品交叉比價，不宜只用行政區平均價判斷單一物件。"
        )

    # 路段開發重點：每區第一名
    route_targets = []
    for district in names:
        routes = districts[district].get("routes", [])
        if routes:
            top = routes[0]
            route_targets.append(
                f"{district}：{top.get('route', '未命名路段')} "
                f"（{top.get('count', 0)}筆／熱度 {money(top.get('heat'))}）"
            )

    route_text = "；".join(route_targets) if route_targets else "目前沒有足夠路段資料。"

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------
    metric_cards = ""

    for district in names:
        m = metrics[district]
        c3 = m["recent3"]["change"]
        c6 = m["recent6"]["change"]
        c12 = m["recent12"]["change"]

        c3_text = "—" if c3 is None else f"{c3:+.2f}%"
        c6_text = "—" if c6 is None else f"{c6:+.2f}%"
        c12_text = "—" if c12 is None else f"{c12:+.2f}%"

        metric_cards += f"""
        <div class="decision-card">
            <div class="decision-card-title">{html_escape(district)}</div>
            <div class="decision-row">
                <span>交易量</span>
                <strong>{m['count']:,} 筆</strong>
            </div>
            <div class="decision-row">
                <span>平均單價</span>
                <strong>{money(m['average'])} 萬／坪</strong>
            </div>
            <div class="decision-row">
                <span>近3個有資料月份</span>
                <strong>{c3_text}</strong>
            </div>
            <div class="decision-row">
                <span>近6個有資料月份</span>
                <strong>{c6_text}</strong>
            </div>
            <div class="decision-row">
                <span>近12個有資料月份</span>
                <strong>{c12_text}</strong>
            </div>
        </div>
        """

    alert_html = "".join(
        f"<li>{html_escape(item)}</li>"
        for item in alerts
    )

    return f"""
    <section class="decision-dashboard">
        <h2>🎯 房仲實戰決策儀表板</h2>

        <div class="decision-summary">
            <div class="decision-summary-card">
                <div class="decision-summary-title">📊 交易量</div>
                <div>{html_escape(volume_text)}</div>
                <small>合計 {total_volume:,} 筆</small>
            </div>

            <div class="decision-summary-card">
                <div class="decision-summary-title">💰 價格差距</div>
                <div>{html_escape(price_gap_text)}</div>
            </div>

            <div class="decision-summary-card">
                <div class="decision-summary-title">🔥 開發路段</div>
                <div>{html_escape(route_text)}</div>
            </div>
        </div>

        <div class="decision-metrics">
            {metric_cards}
        </div>

        <div class="decision-grid">
            <div class="decision-panel seller">
                <h3>🏠 賣方策略</h3>
                <p>{html_escape(seller_advice)}</p>
            </div>

            <div class="decision-panel buyer">
                <h3>🔎 買方策略</h3>
                <p>{html_escape(buyer_advice)}</p>
            </div>

            <div class="decision-panel developer">
                <h3>📞 房仲開發重點</h3>
                <p>
                    優先追蹤交易量高、近期價格有明顯變化的路段，
                    並將同路段成交案例整理成屋主可理解的價格帶。
                    目前重點：{html_escape(route_text)}
                </p>
            </div>
        </div>

        <div class="decision-alerts">
            <h3>🚨 今日市場警示</h3>
            <ul>{alert_html}</ul>
        </div>

        <div class="analysis-note">
            📌 本區塊為資料分析輔助，不代表單一物件的估價；實際委託開發仍應搭配屋齡、
            樓層、格局、管理、車位、路段及個案成交條件。
        </div>
    </section>
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


def build_stage12_alerts(report):
    """
    第12階段：
    路段異常警報＋房仲開發名單。
    所有數字均由 report 動態計算。
    """
    rows = []
    alerts = []
    development = []

    for district, data in report.get("districts", {}).items():
        for item in data.get("route_monitor", []):
            item = dict(item)
            item["district"] = district
            development.append(item)

            price_change = item.get("price_change")
            volume_change = item.get("volume_change")
            latest_count = item.get("latest_count", 0)

            if (
                price_change is not None
                and price_change <= -10
                and latest_count >= 2
                and (item.get("route_age_months") is None or item.get("route_age_months") <= 3)
            ):
                alerts.append({
                    "level": "高",
                    "district": district,
                    "route": item["route"],
                    "message": (
                        f"{district}{item['route']}最新月份平均單價"
                        f"{price_change:+.2f}%，出現明顯短期價格修正訊號。"
                    ),
                    "reason": "至少2筆最新月份交易",
                })

            if (
                volume_change is not None
                and volume_change >= 100
                and latest_count >= 2
                and (item.get("route_age_months") is None or item.get("route_age_months") <= 3)
            ):
                alerts.append({
                    "level": "中",
                    "district": district,
                    "route": item["route"],
                    "message": (
                        f"{district}{item['route']}最新月份交易量"
                        f"{volume_change:+.0f}%，交易活躍度明顯增加。"
                    ),
                    "reason": "與前一有資料月份比較",
                })

            gap = item.get("price_gap_vs_district_median")
            if (
                gap is not None
                and gap <= -15
                and latest_count >= 2
                and (item.get("route_age_months") is None or item.get("route_age_months") <= 3)
            ):
                alerts.append({
                    "level": "中",
                    "district": district,
                    "route": item["route"],
                    "message": (
                        f"{district}{item['route']}平均單價約比行政區中位數低"
                        f"{abs(gap):.1f}%，可列入價格帶研究名單。"
                    ),
                    "reason": "路段平均價與行政區中位數比較",
                })

    development.sort(
        key=lambda x: x.get("development_score", 0),
        reverse=True
    )

    top_development = development[:10]

    if not top_development:
        return """
        <section class="stage12">
            <h2>🚨 房市異常警報＋房仲開發名單</h2>
            <div class="analysis-note">
                目前沒有足夠的路段資料產生第12階段分析。
            </div>
        </section>
        """

    alert_rows = ""
    for index, item in enumerate(alerts[:12], start=1):
        level = item["level"]
        level_class = (
            "alert-high" if level == "高"
            else "alert-medium"
        )

        alert_rows += f"""
        <tr>
            <td>{index}</td>
            <td>{html_escape(item['district'])}</td>
            <td>{html_escape(item['route'])}</td>
            <td>
                <span class="alert-badge {level_class}">
                    {level}
                </span>
            </td>
            <td>{html_escape(item['message'])}</td>
            <td>{html_escape(item['reason'])}</td>
        </tr>
        """

    if not alert_rows:
        alert_rows = """
        <tr>
            <td colspan="6">
                目前沒有達到警報門檻的路段。
                這不代表市場沒有變化，而是目前資料未達到設定的異常門檻。
            </td>
        </tr>
        """

    development_rows = ""
    for index, item in enumerate(top_development, start=1):
        price_change = item.get("price_change")
        volume_change = item.get("volume_change")

        price_text = (
            "—"
            if price_change is None
            else f"{price_change:+.2f}%"
        )

        volume_text = (
            "—"
            if volume_change is None
            else f"{volume_change:+.0f}%"
        )

        age = item.get("route_age_months")
        if age is None:
            age_text = "—"
        elif age == 0:
            age_text = "本期"
        else:
            age_text = f"{age}個月前"

        development_rows += f"""
        <tr>
            <td><strong>{index}</strong></td>
            <td>{html_escape(item['district'])}</td>
            <td><strong>{html_escape(item['route'])}</strong></td>
            <td>{item.get('count', 0)} 筆</td>
            <td>{money(item.get('average'))}</td>
            <td>{price_text}</td>
            <td>{volume_text}</td>
            <td>{age_text}</td>
            <td>
                <strong class="score">
                    {item.get('development_score', 0):.1f}
                </strong>
            </td>
        </tr>
        """

    top = top_development[0]

    if alerts:
        action_text = (
            f"目前共有 {len(alerts)} 個路段達到異常警報門檻，"
            "建議優先檢查成交明細與同路段競品。"
        )
    else:
        action_text = (
            "目前沒有路段達到異常警報門檻，"
            "建議以開發分數較高的路段作為日常追蹤重點。"
        )

    return f"""
    <section class="stage12">

        <h2>🚨 第12階段｜房市異常警報＋房仲開發名單</h2>

        <div class="stage12-summary">
            <div class="stage12-card">
                <div class="stage12-title">🚨 異常警報</div>
                <div class="stage12-value">{len(alerts)}</div>
                <div>個路段</div>
            </div>

            <div class="stage12-card">
                <div class="stage12-title">🔥 第一開發優先</div>
                <div class="stage12-value">
                    {html_escape(top['route'])}
                </div>
                <div>
                    {html_escape(top['district'])}
                </div>
            </div>

            <div class="stage12-card">
                <div class="stage12-title">🎯 開發分數</div>
                <div class="stage12-value">
                    {top.get('development_score', 0):.1f}
                </div>
                <div>滿分100</div>
            </div>

            <div class="stage12-card">
                <div class="stage12-title">📊 監控路段</div>
                <div class="stage12-value">
                    {len(development)}
                </div>
                <div>個</div>
            </div>
        </div>

        <div class="stage12-action">
            <strong>📞 今日房仲行動：</strong>
            {html_escape(action_text)}
        </div>

        <h3>🚨 路段異常警報</h3>

        <div class="table-scroll">
        <table class="stage12-table">
            <tr>
                <th>排名</th>
                <th>行政區</th>
                <th>路段</th>
                <th>等級</th>
                <th>警報內容</th>
                <th>判斷依據</th>
            </tr>
            {alert_rows}
        </table>
        </div>

        <h3>🔥 今日房仲開發優先名單 Top 10</h3>

        <div class="table-scroll">
        <table class="stage12-table">
            <tr>
                <th>排名</th>
                <th>行政區</th>
                <th>路段</th>
                <th>交易量</th>
                <th>平均單價</th>
                <th>最新價格變化</th>
                <th>交易量變化</th>
                <th>資料新鮮度</th>
                <th>開發分數</th>
            </tr>
            {development_rows}
        </table>
        </div>

        <div class="stage12-note">
            ⚠️ 本階段屬於「路段監控與開發排序」，不是單一物件估價。
            價格異常必須再搭配屋齡、樓層、坪數、格局、車位及個案條件確認。
            若最新月份交易筆數過少，系統會降低警報判斷的可信度。
        </div>

    </section>
    """



# ============================================================
# 第14階段：市場機會雷達＋房仲開發行動建議
# ============================================================

def build_opportunity_data(report):
    """
    將既有路段監控資料轉成「市場機會分數」。

    這是房仲內部的開發排序工具，不是單一物件估價。
    分數綜合：交易活躍度、資料新鮮度、量能變化、價格修正、
    相對行政區價格位置；並產生可直接執行的開發理由。
    """
    district_results = []
    route_results = []

    for district, data in report.get("districts", {}).items():
        stats = data.get("stats", {})
        routes = data.get("route_monitor", []) or []
        trend = data.get("trend", {}) or {}

        count = int(stats.get("count") or 0)
        avg = to_float(stats.get("average_price"))
        median_price = to_float(stats.get("median_price"))
        recent_change = to_float(trend.get("change"))
        confidence = trend.get("confidence", "低")

        # 行政區機會分數：用於士林／北投比較，不代表房價高低。
        volume_score = min(count / 30, 1.0) * 30
        freshness_scores = []
        for r in routes:
            age = r.get("route_age_months")
            if age is None:
                freshness_scores.append(0)
            elif age <= 1:
                freshness_scores.append(20)
            elif age <= 3:
                freshness_scores.append(16)
            elif age <= 6:
                freshness_scores.append(10)
            else:
                freshness_scores.append(4)
        freshness_score = max(freshness_scores, default=0)

        if recent_change is None:
            trend_score = 8
        elif -10 <= recent_change <= 5:
            trend_score = 20
        elif recent_change < -10:
            trend_score = 15
        else:
            trend_score = 12

        active_route_count = sum(1 for r in routes if (r.get("latest_count") or 0) >= 2)
        route_score = min(active_route_count / 5, 1.0) * 20
        confidence_score = {"高": 10, "中": 7, "低": 4}.get(confidence, 4)

        district_score = round(
            min(30, volume_score)
            + freshness_score
            + trend_score
            + route_score
            + confidence_score,
            1,
        )

        district_results.append({
            "district": district,
            "score": district_score,
            "count": count,
            "average": avg,
            "median": median_price,
            "recent_change": recent_change,
            "confidence": confidence,
            "active_routes": active_route_count,
        })

        for route in routes:
            item = dict(route)
            price_change = to_float(item.get("price_change"))
            volume_change = to_float(item.get("volume_change"))
            latest_count = int(item.get("latest_count") or 0)
            gap = to_float(item.get("price_gap_vs_district_median"))
            age = item.get("route_age_months")

            activity = min((item.get("count") or 0) / 8, 1.0) * 30

            if age is None:
                freshness = 4
            elif age <= 1:
                freshness = 20
            elif age <= 3:
                freshness = 16
            elif age <= 6:
                freshness = 10
            else:
                freshness = 4

            if volume_change is None or latest_count < 2:
                volume_score = 5
            elif volume_change >= 100:
                volume_score = 15
            elif volume_change >= 50:
                volume_score = 12
            elif volume_change >= 20:
                volume_score = 9
            elif volume_change >= 0:
                volume_score = 7
            else:
                volume_score = 4

            # 「價格修正＋仍有交易」視為房仲值得研究的開發訊號，
            # 不是判定房價一定會反彈。
            if price_change is None:
                price_score = 6
            elif -20 <= price_change <= -5 and latest_count >= 2:
                price_score = 20
            elif price_change < -20 and latest_count >= 2:
                price_score = 14
            elif 5 <= price_change <= 15 and latest_count >= 2:
                price_score = 10
            else:
                price_score = 7

            if gap is not None and gap <= -15:
                relative_score = 15
            elif gap is not None and gap <= -5:
                relative_score = 11
            elif gap is not None and gap <= 5:
                relative_score = 8
            else:
                relative_score = 5

            score = round(
                activity + freshness + volume_score + price_score + relative_score,
                1,
            )

            reasons = []
            actions = []
            if latest_count >= 2:
                reasons.append(f"最新月份{latest_count}筆交易")
            if volume_change is not None and volume_change >= 50:
                reasons.append(f"量能{volume_change:+.0f}%")
                actions.append("優先追蹤近期新增案源")
            if price_change is not None and -20 <= price_change <= -5 and latest_count >= 2:
                reasons.append(f"短期價格修正{price_change:+.1f}%")
                actions.append("研究議價空間與同路段競品")
            if gap is not None and gap <= -15:
                reasons.append(f"低於行政區中位數{abs(gap):.1f}%")
                actions.append("建立價格帶／低總價開發名單")
            if age is not None and age <= 1:
                reasons.append("資料新鮮")
                actions.append("優先安排屋主／市場接觸")

            if not reasons:
                reasons.append("交易資料可追蹤")
            if not actions:
                actions.append("持續觀察，不急於下結論")

            if score >= 75:
                priority = "A｜立即追蹤"
            elif score >= 60:
                priority = "B｜本週追蹤"
            else:
                priority = "C｜一般觀察"

            item.update({
                "district": district,
                "opportunity_score": score,
                "priority": priority,
                "opportunity_reasons": reasons,
                "recommended_actions": actions,
            })
            route_results.append(item)

    district_results.sort(key=lambda x: x["score"], reverse=True)
    route_results.sort(key=lambda x: x["opportunity_score"], reverse=True)

    return {
        "districts": district_results,
        "routes": route_results[:20],
    }


def build_stage14_opportunity_board(report):
    """建立第14階段市場機會雷達 HTML。"""
    opportunity = build_opportunity_data(report)
    districts = opportunity.get("districts", [])
    routes = opportunity.get("routes", [])

    if not districts and not routes:
        return """
        <section class="stage14">
            <h2>🎯 第14階段｜市場機會雷達</h2>
            <div class="analysis-note">目前沒有足夠資料建立市場機會排序。</div>
        </section>
        """

    district_cards = ""
    for item in districts:
        change = item.get("recent_change")
        change_text = "—" if change is None else f"{change:+.2f}%"
        district_cards += f"""
        <div class="stage14-district-card">
            <div class="stage14-card-title">{html_escape(item['district'])}</div>
            <div class="stage14-score">{item['score']:.1f}<small>/100</small></div>
            <div>交易量：{item['count']} 筆</div>
            <div>近期價格變化：{change_text}</div>
            <div>活躍路段：{item['active_routes']} 個</div>
            <div>樣本可信度：{html_escape(item['confidence'])}</div>
        </div>
        """

    route_rows = ""
    for index, item in enumerate(routes[:10], start=1):
        reasons = "；".join(item.get("opportunity_reasons", [])[:3])
        actions = "；".join(item.get("recommended_actions", [])[:2])
        score = item.get("opportunity_score", 0)
        priority = item.get("priority", "C｜一般觀察")
        badge_class = "stage14-a" if priority.startswith("A") else ("stage14-b" if priority.startswith("B") else "stage14-c")
        route_rows += f"""
        <tr>
            <td><strong>{index}</strong></td>
            <td>{html_escape(item.get('district'))}</td>
            <td><strong>{html_escape(item.get('route'))}</strong></td>
            <td>{item.get('count', 0)} 筆</td>
            <td>{money(item.get('average'))}</td>
            <td><strong class="stage14-score-text">{score:.1f}</strong></td>
            <td><span class="stage14-badge {badge_class}">{html_escape(priority)}</span></td>
            <td>{html_escape(reasons)}</td>
            <td>{html_escape(actions)}</td>
        </tr>
        """

    top = routes[0] if routes else None
    if top:
        action = (
            f"今日第一優先：{top['district']} × {top['route']}，"
            f"機會分數 {top['opportunity_score']:.1f}。"
            "若實際案源條件吻合，建議先查同路段近期成交與在售競品，再安排開發。"
        )
    else:
        action = "目前沒有足夠路段資料，先以行政區機會分數與熱門路段持續觀察。"

    return f"""
    <section class="stage14">
        <h2>🎯 第14階段｜市場機會雷達＋房仲開發行動</h2>

        <div class="stage14-action">
            <strong>📞 今日行動：</strong>{html_escape(action)}
        </div>

        <h3>🏆 士林／北投市場機會分數</h3>
        <div class="stage14-district-grid">
            {district_cards}
        </div>

        <h3>🔥 今日房仲開發機會 Top 10</h3>
        <div class="table-scroll">
        <table class="stage14-table">
            <tr>
                <th>排名</th>
                <th>行政區</th>
                <th>路段</th>
                <th>交易量</th>
                <th>平均單價</th>
                <th>機會分數</th>
                <th>優先級</th>
                <th>主要訊號</th>
                <th>建議行動</th>
            </tr>
            {route_rows or '<tr><td colspan="9">目前沒有足夠路段資料。</td></tr>'}
        </table>
        </div>

        <div class="stage14-note">
            ⚠️ 機會分數是「房仲開發排序模型」，不是物件估價，也不是投資報酬率預測。
            分數越高代表目前資料呈現較值得優先研究的路段；實際開發仍需核對屋齡、樓層、坪數、格局、車位、產品類型與個案成交條件。
        </div>
    </section>
    """


def build_trend_and_price_band_section(report):
    """建立多期間趨勢與價格帶分析區塊。"""
    sections = []

    for district in TARGET_DISTRICTS:
        data = report.get("districts", {}).get(district)
        if not data:
            continue

        windows = data.get("trend_windows", {})
        bands = data.get("price_bands", [])
        latest = data.get("latest_transaction_date")

        trend_rows = ""
        for window in (3, 6, 12):
            info = windows.get(str(window), {})
            count = info.get("count", 0)
            change = info.get("change")
            start_month = info.get("start_month") or "—"
            end_month = info.get("end_month") or "—"
            latest_count = info.get("latest_count", 0)

            change_text = "資料不足"
            if change is not None:
                change_text = f"{change:+.2f}%"

            period_text = (
                f"{start_month} → {end_month}"
                if count >= 2 else
                "有效月份不足，無法比較"
            )

            trend_rows += f"""
                <tr>
                    <td>近{window}個有資料月份</td>
                    <td>{count} 個</td>
                    <td>{html_escape(period_text)}</td>
                    <td>{change_text}</td>
                    <td>{latest_count} 筆</td>
                </tr>
            """

        band_rows = ""
        for band in bands:
            share = band.get("share")
            share_text = "—" if share is None else f"{share:.1f}%"
            average = band.get("average")

            band_rows += f"""
                <tr>
                    <td>{html_escape(band.get("band", "—"))}</td>
                    <td>{band.get("count", 0):,} 筆</td>
                    <td>{share_text}</td>
                    <td>{money(average)}</td>
                </tr>
            """

        top_band = build_price_band_summary(bands)
        if top_band:
            top_band_text = (
                f"目前交易量最高價格帶為「{html_escape(top_band['band'])}」，"
                f"{top_band['count']:,} 筆，占全部有效交易 "
                f"{top_band.get('share', 0):.1f}%。"
            )
        else:
            top_band_text = "目前沒有足夠交易資料建立價格帶分布。"

        sections.append(f"""
        <section class="trend-band-section">
            <h2>📊 {html_escape(district)}｜3／6／12月趨勢＋價格帶分析</h2>

            <div class="trend-band-grid">
                <div>
                    <h3>📈 多期間價格趨勢</h3>
                    <div class="table-scroll">
                    <table>
                        <tr>
                            <th>觀察期間</th>
                            <th>有效月份</th>
                            <th>比較區間</th>
                            <th>價格變化</th>
                            <th>最新月交易量</th>
                        </tr>
                        {trend_rows}
                    </table>
                    </div>
                    <p class="analysis-note">
                        ⚠️ 以上以「最近N個有資料月份」計算；若月份不連續，不視為連續月數。
                        價格變化為第一個有效月份與最新有效月份的平均單價比較。
                    </p>
                </div>

                <div>
                    <h3>💰 單價價格帶分布</h3>
                    <div class="table-scroll">
                    <table>
                        <tr>
                            <th>價格帶（萬元／坪）</th>
                            <th>交易量</th>
                            <th>占比</th>
                            <th>該價格帶平均</th>
                        </tr>
                        {band_rows}
                    </table>
                    </div>
                    <div class="band-highlight">
                        🔎 {top_band_text}
                    </div>
                </div>
            </div>
        </section>
        """)

    if not sections:
        return """
        <section class="trend-band-section">
            <h2>📊 3／6／12月趨勢＋價格帶分析</h2>
            <div class="analysis-note">目前沒有足夠行政區資料可分析。</div>
        </section>
        """

    return "".join(sections)


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
    decision_dashboard = build_decision_dashboard(report)
    trend_band_analysis = build_trend_and_price_band_section(report)
    stage12_alerts = build_stage12_alerts(report)
    stage14_opportunity = build_stage14_opportunity_board(report)

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

            <div class="district-mini-analysis">
                <h3>📊 3／6／12個有資料月份</h3>
                <div class="mini-period-grid">
                    <div class="mini-period">
                        <span>近3月</span>
                        <strong>{(data.get("trend_windows", {}).get("3", {}).get("change") is None and "—") or f"{data.get("trend_windows", {}).get("3", {}).get("change"):+.2f}%"}</strong>
                    </div>
                    <div class="mini-period">
                        <span>近6月</span>
                        <strong>{(data.get("trend_windows", {}).get("6", {}).get("change") is None and "—") or f"{data.get("trend_windows", {}).get("6", {}).get("change"):+.2f}%"}</strong>
                    </div>
                    <div class="mini-period">
                        <span>近12月</span>
                        <strong>{(data.get("trend_windows", {}).get("12", {}).get("change") is None and "—") or f"{data.get("trend_windows", {}).get("12", {}).get("change"):+.2f}%"}</strong>
                    </div>
                </div>
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


.decision-dashboard {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.decision-dashboard h2 {{
    margin-top: 0;
}}

.decision-summary {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 18px;
}}

.decision-summary-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.7;
}}

.decision-summary-title {{
    color: #1d4ed8;
    font-weight: 700;
    margin-bottom: 6px;
}}

.decision-summary-card small {{
    color: #64748b;
}}

.decision-metrics {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin-bottom: 18px;
}}

.decision-card {{
    background: #f8fafc;
    border: 1px solid #dbeafe;
    border-radius: 10px;
    padding: 16px;
}}

.decision-card-title {{
    color: #0f172a;
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 10px;
}}

.decision-row {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 7px 0;
    border-bottom: 1px solid #e5e7eb;
}}

.decision-row:last-child {{
    border-bottom: 0;
}}

.decision-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 18px 0;
}}

.decision-panel {{
    padding: 18px;
    border-radius: 10px;
    line-height: 1.8;
}}

.decision-panel h3 {{
    margin-top: 0;
}}

.decision-panel.seller {{
    background: #fff7ed;
    border-left: 5px solid #f97316;
}}

.decision-panel.buyer {{
    background: #eff6ff;
    border-left: 5px solid #2563eb;
}}

.decision-panel.developer {{
    background: #f0fdf4;
    border-left: 5px solid #16a34a;
}}

.decision-alerts {{
    margin-top: 18px;
    padding: 18px;
    background: #f8fafc;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
}}

.decision-alerts h3 {{
    margin-top: 0;
}}

.decision-alerts li {{
    margin-bottom: 8px;
}}


.stage14 {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07);
}}

.stage14 h2 {{
    margin-top: 0;
}}

.stage14-action {{
    margin: 18px 0;
    padding: 18px;
    background: #eff6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.8;
}}

.stage14-district-grid {{
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    margin: 18px 0 22px 0;
}}

.stage14-district-card {{
    background: #f8fafc;
    border: 1px solid #dbeafe;
    border-radius: 10px;
    padding: 18px;
    line-height: 1.8;
}}

.stage14-card-title {{
    font-size: 20px;
    font-weight: 800;
    color: #0f172a;
}}

.stage14-score {{
    margin: 4px 0 8px 0;
    font-size: 34px;
    font-weight: 900;
    color: #1d4ed8;
}}

.stage14-score small {{
    font-size: 13px;
    color: #64748b;
    margin-left: 4px;
}}

.stage14-table td, .stage14-table th {{
    vertical-align: top;
}}

.stage14-badge {{
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
}}

.stage14-a {{
    background: #fee2e2;
    color: #b91c1c;
}}

.stage14-b {{
    background: #fef3c7;
    color: #92400e;
}}

.stage14-c {{
    background: #e2e8f0;
    color: #475569;
}}

.stage14-score-text {{
    color: #1d4ed8;
}}

.stage14-note {{
    margin-top: 18px;
    padding: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    color: #64748b;
    line-height: 1.7;
}}


.stage12 {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07);
}}

.stage12 h2 {{
    margin-top: 0;
}}

.stage12 h3 {{
    margin-top: 24px;
}}

.stage12-summary {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin: 18px 0;
}}

.stage12-card {{
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 16px;
    line-height: 1.6;
}}

.stage12-title {{
    color: #1d4ed8;
    font-weight: 700;
}}

.stage12-value {{
    margin-top: 6px;
    font-size: 24px;
    font-weight: 800;
    color: #0f172a;
}}

.stage12-action {{
    margin: 18px 0;
    padding: 18px;
    background: #eff6ff;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    line-height: 1.8;
}}

.stage12-table {{
    margin-bottom: 18px;
}}

.alert-badge {{
    display: inline-block;
    padding: 3px 9px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
}}

.alert-high {{
    background: #fee2e2;
    color: #b91c1c;
}}

.alert-medium {{
    background: #fef3c7;
    color: #92400e;
}}

.score {{
    color: #1d4ed8;
}}

.stage12-note {{
    margin-top: 18px;
    padding: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    color: #64748b;
    line-height: 1.7;
}}

.table-scroll {{
    overflow-x: auto;
}}


.trend-band-section {{
    margin: 25px 0 30px 0;
    padding: 24px;
    background: #ffffff;
    border-radius: 14px;
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.06);
}}

.trend-band-section h2 {{
    margin-top: 0;
}}

.trend-band-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
}}

.band-highlight {{
    margin-top: 12px;
    padding: 14px;
    background: #eff6ff;
    border-left: 4px solid #2563eb;
    border-radius: 8px;
    line-height: 1.7;
}}

.district-mini-analysis {{
    margin: 18px 0;
    padding: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}}

.district-mini-analysis h3 {{
    margin-top: 0;
}}

.mini-period-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
}}

.mini-period {{
    padding: 12px;
    background: #ffffff;
    border: 1px solid #dbeafe;
    border-radius: 8px;
}}

.mini-period span {{
    display: block;
    color: #64748b;
    font-size: 13px;
}}

.mini-period strong {{
    display: block;
    margin-top: 5px;
    font-size: 18px;
    color: #1d4ed8;
}}

@media(max-width:700px) {{

    .district {{
        padding: 15px;
    }}

    table {{
        font-size: 13px;
    }}

    .trend-band-grid {{
        grid-template-columns: 1fr;
    }}

    .mini-period-grid {{
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

        {decision_dashboard}

        {trend_band_analysis}

        {stage14_opportunity}

        {stage12_alerts}

        {cards}

    </div>

<footer>

台北市士林區／北投區房市監控系統<br>

第十四階段：房市監控＋市場機會雷達＋房仲開發行動

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
    print("第十四階段房市報告完成")
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
