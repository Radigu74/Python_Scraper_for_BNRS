import os
import json
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import smtplib
from email.message import EmailMessage
from playwright.async_api import async_playwright

print("▶️ Starting scraper...")

try:
    # Recreate credentials
    json_str = os.getenv("GOOGLE_CREDS_JSON")
    if not json_str:
        raise ValueError("❌ GOOGLE_CREDS_JSON environment variable is missing!")
    with open("client_secret.json", "w") as f:
        f.write(json_str)
    print("✅ Credentials loaded")

    # Google Sheets Setup
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("client_secret.json", scope)
    client = gspread.authorize(creds)

    spreadsheet_id = "DTI_BNRS_Leads"
    sheet = client.open("DTI_BNRS_Leads").sheet1
    existing_names = set(row[0] for row in sheet.get_all_values()[1:])
    print(f"📄 Loaded sheet, {len(existing_names)} existing entries")

    keywords = ["trading", "services", "construction"]
    new_entries = []

    async def scrape_bnrs():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            for keyword in keywords:
                print(f"🔍 Searching BNRS for keyword: {keyword}")
                url = f"https://bnrs.dti.gov.ph/search?keyword={keyword}"
                await page.goto(url)
                await page.wait_for_timeout(4000)

                for _ in range(3):
                    html = await page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    rows = soup.find_all("tr", {"class": "ng-scope"})

                    for row in rows:
                        cols = row.find_all("td")
                        if len(cols) >= 4:
                            name = cols[0].text.strip()
                            if name not in existing_names:
                                business = {
                                    "Business Name": name,
                                    "Business Scope": cols[1].text.strip(),
                                    "Business Location": cols[2].text.strip(),
                                    "Date Registered": cols[3].text.strip()
                                }
                                new_entries.append(business)
                                existing_names.add(name)

                    try:
                        next_button = await page.query_selector("a[ng-click='nextPage()']")
                        if next_button:
                            await next_button.click()
                            await page.wait_for_timeout(2000)
                        else:
                            break
                    except Exception as e:
                        print(f"⚠️ BNRS pagination failed: {e}")
                        break

            await browser.close()

    async def scrape_sec_crs():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            print("🔍 Accessing SEC CRS")

            await page.goto("https://crs.sec.gov.ph/#!/", wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            try:
                search_box = await page.wait_for_selector("input[placeholder='Search Business Name']", timeout=10000)
                await search_box.fill("trading")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(5000)

                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")
                results = soup.find_all("div", class_="company-result")

                for result in results:
                    name_el = result.find("h4")
                    if name_el:
                        name = name_el.get_text(strip=True)
                        if name not in existing_names:
                            business = {
                                "Business Name": name,
                                "Business Scope": "N/A",
                                "Business Location": "N/A",
                                "Date Registered": "N/A"
                            }
                            new_entries.append(business)
                            existing_names.add(name)
            except Exception as e:
                print(f"⚠️ SEC scraping failed: {e}")

            await browser.close()

    async def main():
        await scrape_bnrs()
        await scrape_sec_crs()

    asyncio.run(main())
    print(f"🧹 Scraped {len(new_entries)} new entries")

    for entry in new_entries:
        sheet.append_row([
            entry["Business Name"],
            entry["Business Scope"],
            entry["Business Location"],
            entry["Date Registered"]
        ])
    print("📤 Uploaded new entries to Google Sheets")

    if new_entries:
        msg = EmailMessage()
        msg["Subject"] = "New DTI Business Leads Added"
        msg["From"] = os.getenv("ALERT_EMAIL")
        msg["To"] = os.getenv("ALERT_RECEIVER")
        msg.set_content(f"{len(new_entries)} new business leads were added to your Google Sheet.")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(os.getenv("ALERT_EMAIL"), os.getenv("ALERT_PASSWORD"))
            smtp.send_message(msg)
        print("✉️ Alert email sent.")

    print("✅ Scraping and upload complete.")

except Exception as e:
    print("❌ An error occurred:", str(e))
