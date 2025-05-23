import os
import csv
import smtplib
import sqlite3
from datetime import datetime
from email.message import EmailMessage
from io import StringIO

import requests
from bs4 import BeautifulSoup

from dotenv import load_dotenv

load_dotenv()  # Loads from .env
# Configurable constants (can be overridden by env)
RATE_TYPE = os.getenv("RATE_TYPE", "Fixed")
TERM_LENGTH = int(os.getenv("TERM_LENGTH", 12))
AVG_MONTHLY_KWH = float(os.getenv("AVG_MONTHLY_KWH", 1000))
CURRENT_PRICE_PER_KWH = float(os.getenv("CURRENT_PRICE_PER_KWH", 0.09))
CURRENT_MONTHLY_FEE = float(os.getenv("CURRENT_MONTHLY_FEE", 5.00))
NOTIFY_BELOW_SAVINGS = float(os.getenv("NOTIFY_BELOW_SAVINGS", 10.00))
DB_PATH = os.getenv("DB_PATH", "data/energy_rates.db")

EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_SMTP = os.getenv("EMAIL_SMTP")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

URL = "https://energychoice.ohio.gov/ApplesToApplesComparision.aspx?Category=Electric&TerritoryId=7&RateCode=1"

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
}

def fetch_csv():
    s = requests.Session()
    r = s.get(URL, headers=HEADERS)
    soup = BeautifulSoup(r.text, 'html.parser')

    viewstate = soup.select_one("#__VIEWSTATE")["value"]
    eventvalidation = soup.select_one("#__EVENTVALIDATION")["value"]

    payload = {
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$lnkExportToCSV",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": viewstate,
        "__EVENTVALIDATION": eventvalidation
    }

    post = s.post(URL, data=payload, headers=HEADERS)
    return post.text

def parse_csv(csv_data):
    rows = []
    reader = csv.DictReader(StringIO(csv_data), delimiter=',')
    current_cost = (CURRENT_PRICE_PER_KWH * AVG_MONTHLY_KWH) + CURRENT_MONTHLY_FEE
    
    for row in reader:
        try:
            # Filter based on user preference
            if RATE_TYPE and row['RateType'] != RATE_TYPE:
                continue
            if TERM_LENGTH and int(row['TermLength']) < TERM_LENGTH:
                continue
            price = float(row['Price'])
            monthly_fee = float(row['MonthlyFee']) if row['MonthlyFee'] else 0
            # Calculate the estimated cost for this vendor
            est_cost = (price * AVG_MONTHLY_KWH) + monthly_fee
            savings = current_cost - est_cost
            row['EstimatedMonthlyCost'] = est_cost
            row['SavingsVsCurrent'] = savings
            row['Date'] = datetime.today().strftime('%Y-%m-%d')
            rows.append(row)
        except Exception as e:
            print(f"Skipping row due to error: {e}")
    return rows

def store_rows(rows):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id INTEGER PRIMARY KEY,
            date TEXT,
            supplier_company TEXT,
            display_company TEXT,
            price REAL,
            rate_type TEXT,
            is_intro_offer INTEGER,
            intro_offer_details TEXT,
            term_length INTEGER,
            early_term_fee TEXT,
            monthly_fee REAL,
            is_promo_offer INTEGER,
            promo_offer_details TEXT,
            estimated_monthly_cost REAL,
            savings_vs_current REAL
        )
    """)

    for row in rows:
        cur.execute("""
            INSERT INTO rates (
                date, supplier_company, display_company, price, rate_type,
                is_intro_offer, intro_offer_details, term_length, early_term_fee,
                monthly_fee, is_promo_offer, promo_offer_details,
                estimated_monthly_cost, savings_vs_current
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['Date'], row['SupplierCompanyName'], row['CompanyName'],
            float(row['Price']), row['RateType'],
            int(row['IsIntroductoryOffer'] == 'Yes'), row['IntroductoryOfferDetails'],
            int(row['TermLength']), row['EarlyTerminationFee'],
            float(row['MonthlyFee'] or 0), int(row['IsPromotionalOffer'] == 'Yes'),
            row['PromotionalOfferDetails'], row['EstimatedMonthlyCost'],
            row['SavingsVsCurrent']
        ))

    conn.commit()
    conn.close()

def send_email(matches):
    if not EMAIL_FROM or not EMAIL_TO or not EMAIL_USER or not EMAIL_PASS:
        print("Email settings not configured, skipping email.")
        return
    print("email!")
    return
    msg = EmailMessage()
    msg["Subject"] = "⚡ New Cheap Electricity Plans Found"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["From"] = f"Frugal Bot <{SMTP_USERNAME}>"
    lines = [
        f"Found {len(matches)} plans cheaper than current setup:",
        ""
    ]
    for r in matches:
        lines.append(f"{r['CompanyName']} - ${r['Price']}/kWh, ${r['MonthlyFee']} fee, saves ${round(r['SavingsVsCurrent'], 2)}")

    msg.set_content("\n".join(lines))

    with smtplib.SMTP(EMAIL_SMTP, EMAIL_PORT) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

def main():
    print("Fetching CSV...")
    raw = fetch_csv()
    print("Parsing rows...")
    rows = parse_csv(raw)
    matches = [r for r in rows if r['SavingsVsCurrent'] >= NOTIFY_BELOW_SAVINGS]
    print(f"Storing {len(rows)} filtered entries...")
    store_rows(rows)
    if matches:
        print(f"Sending email for {len(matches)} matches...")
        send_email(matches)
    else:
        print("No matches found worth emailing.")

if __name__ == '__main__':
    main()
