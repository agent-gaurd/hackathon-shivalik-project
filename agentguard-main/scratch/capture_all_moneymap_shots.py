import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://localhost:3000"
ARTIFACTS_DIR = r"C:\Users\Dinesh\.gemini\antigravity-ide\brain\cbff0677-3f8c-47fb-8ec9-3ced7265f35a"

ACCOUNTS = [
    ("normal_customer", "acc_1"),
    ("mule", "mule_902cd"),
    ("cashout_account", "sink_cf8ad"),
    ("no_history", "new_user_empty")
]

VIEWPORTS = [
    ("1440px", 1440, 950),
    ("390px", 390, 844)
]

async def capture_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        
        for acc_label, acc_id in ACCOUNTS:
            for vp_label, width, height in VIEWPORTS:
                context = await browser.new_context(viewport={"width": width, "height": height})
                page = await context.new_page()
                
                url = f"{BASE_URL}/?account={acc_id}"
                print(f"Navigating to {url} at {width}x{height}...")
                await page.goto(url)
                
                # Wait for data to load and render
                await page.wait_for_selector(".summary-headline, h1, [data-testid='centre-card'], .stats-strip", timeout=10000)
                await page.wait_for_timeout(1500)
                
                # Save screenshot to artifacts directory
                filename = f"moneymap_{acc_label}_{vp_label}.png"
                out_path = os.path.join(ARTIFACTS_DIR, filename)
                await page.screenshot(path=out_path, full_page=True)
                print(f"Captured: {out_path} ({os.path.getsize(out_path)} bytes)")
                
                await context.close()
                
        await browser.close()
    print("All screenshots successfully captured!")

if __name__ == "__main__":
    asyncio.run(capture_all())
