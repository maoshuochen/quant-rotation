#!/usr/bin/env python3
"""
前端页面截图脚本
"""
from playwright.sync_api import sync_playwright
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

with sync_playwright() as p:
    print("启动浏览器...")
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_viewport_size({"width": 1440, "height": 900})

    print("访问页面...")
    page.goto("http://localhost:4173", wait_until="networkidle", timeout=30000)

    print("等待页面渲染...")
    time.sleep(3)

    # 截图 1 - 总览页面
    print("截图 1: 总览页面")
    page.screenshot(path="screenshot-overview.png", full_page=False)

    # 截图 2 - 点击因子 Tab
    print("截图 2: 因子页面")
    page.click('button:has-text("因子")')
    time.sleep(2)
    page.screenshot(path="screenshot-factors.png", full_page=False)

    # 截图 3 - 点击回测 Tab
    print("截图 3: 回测页面")
    page.click('button:has-text("回测")')
    time.sleep(2)
    page.screenshot(path="screenshot-backtest.png", full_page=False)

    browser.close()
    print("截图完成！")
