# -*- coding: utf-8 -*-

"""
台北市士林區／北投區房市監控系統
主程式

目前版本：
建立基本程式架構，後續會逐步加入
房屋資料蒐集、價格分析與每日自動報告功能。
"""

from datetime import datetime


def main():
    """程式主入口"""

    print("=" * 60)
    print("台北市士林區／北投區房市監控系統")
    print("=" * 60)

    now = datetime.now()

    print(f"程式啟動時間：{now}")
    print("系統目前已成功啟動。")
    print("下一階段將加入房市資料蒐集功能。")


if __name__ == "__main__":
    main()
