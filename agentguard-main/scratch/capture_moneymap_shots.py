import asyncio
import os
from playwright.async_api import async_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://localhost:3000"
ARTIFACTS_DIR = r"C:\Users\Dinesh\.gemini\antigravity-ide\brain\cbff0677-3f8c-47fb-8ec9-3ced7265f35a"

ACCOUNTS = [
    ("normal", "acc_1"),
    ("mule", "mule_902cd"),
    ("cashout", "sink_cf8ad"),
    ("nohistory", "new_user_empty")
]

VIEWPORTS = [
    ("1440", 1440, 950),
    ("390", 390, 844)
]

async def take_screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        
        for acc_label, acc_id in ACCOUNTS:
            for vp_name, width, height in VIEWPORTS:
                context = await browser.new_context(viewport={"width": width, "height": height})
                page = await context.new_page()
                
                print(f"Loading {BASE_URL} for {acc_label} ({acc_id}) at {vp_name}px...")
                await page.goto(BASE_URL)
                await page.wait_for_timeout(1000)
                
                # Select the account using the account picker or directly setting the account
                # Let's see if the account picker can search and click the account
                search_input = page.locator("#account-search-input")
                if await search_input.count() > 0:
                    await search_input.click()
                    await search_input.fill(acc_id)
                    await page.wait_for_timeout(400)
                    # Check if matching account item exists
                    item = page.locator(f"button[data-account-id='{acc_id}']")
                    if await item.count() > 0:
                        await item.first.click()
                        await page.wait_for_timeout(800)
                    else:
                        print(f"Account option {acc_id} not in dropdown, checking custom trigger...")
                        # In case the account is new (like new_user_empty) and not in /v1/accounts list yet,
                        # let's trigger via page.evaluate
                        await page.evaluate(f"(aid) => window.__setMoneyMapAccount && window.__setMoneyMapAccount(aid)", acc_id)
                        await page.wait_for_timeout(800)

                shot_path = os.path.join(ARTIFACTS_DIR, f"moneymap_{acc_label}_{vp_name}px.png")
                await page.screenshot(path=shot_path, full_page=True)
                print(f"Saved: {shot_path}")
                await context.close()
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(take_screenshots())
