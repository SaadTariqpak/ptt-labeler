"""Opens the deployed app in a real browser so Streamlit Community Cloud counts it as traffic and does not put it to sleep.

A plain HTTP request is not enough: the app only counts as used once its page connects over a websocket.
If the app is already asleep, this clicks "Yes, get this app back up!" and waits until the page is there.
"""
import os
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "https://ptt-labeler-lmpmpkwrpdvopou5uakbo6.streamlit.app/")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
    try:
        page.get_by_role("button", name="Yes, get this app back up!").click(timeout=15_000)
        print("app was asleep, wake button clicked")
    except PlaywrightTimeout:
        print("no wake button, app was awake")
    app = page.frame_locator('iframe[title="streamlitApp"]')
    try:
        app.get_by_text("Guess the Mood").first.wait_for(timeout=120_000)
    except PlaywrightTimeout:
        print("app page did not show up in time", file=sys.stderr)
        sys.exit(1)
    print("app is up")
    browser.close()
