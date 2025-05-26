from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.message import EmailMessage
import os
import time

# ---------- Google Sheets Setup ----------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_path = "client_secret.json"  # Load this from env in Railway
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
client = gspread.authorize(creds)
sheet = client.open("DTI_BNRS_Leads").sheet1
existing_names = set(row[0] for row in sheet.get_all_values()[1:])  # Skip headers

# ---------- Selenium Setup ----------
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=chrome_options)

# ---------- Scrape & De-Dupe ----------
keywords = ["trading", "services", "construction"]
new_entries = []

for keyword in keywords:
    url = f"https://bnrs.dti.gov.ph/search?keyword={keyword}"
    driver.get(url)
    time.sleep(4)

    for page in range(1, 4):
        soup = BeautifulSoup(driver.page_source, "html.parser")
        results = soup.find_all("tr", {"class": "ng-scope"})

        for result in results:
            cols = result.find_all("td")
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
            next_button = driver.find_element(By.LINK_TEXT, "Next")
            next_button.click()
            time.sleep(2)
        except:
            break

driver.quit()

# ---------- Save to Google Sheets ----------
for entry in new_entries:
    sheet.append_row([
        entry["Business Name"],
        entry["Business Scope"],
        entry["Business Location"],
        entry["Date Registered"]
    ])

# ---------- Send Email Alert ----------
if new_entries:
    msg = EmailMessage()
    msg["Subject"] = "New DTI Business Leads Added"
    msg["From"] = os.getenv("ALERT_EMAIL")
    msg["To"] = os.getenv("ALERT_RECEIVER")
    msg.set_content(f"{len(new_entries)} new business leads were added to your Google Sheet.")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(os.getenv("ALERT_EMAIL"), os.getenv("ALERT_PASSWORD"))
        smtp.send_message(msg)
