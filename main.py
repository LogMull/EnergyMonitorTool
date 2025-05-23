import requests
from bs4 import BeautifulSoup

URL = "https://energychoice.ohio.gov/ApplesToApplesComparision.aspx?Category=Electric&TerritoryId=7&RateCode=1"
session = requests.Session()

# Step 1: GET the page and extract form data
r = session.get(URL)
soup = BeautifulSoup(r.text, 'html.parser')
form = soup.find("form")

form_data = {i['name']: i.get('value', '') for i in form.find_all("input", {"type": "hidden"})}
form_data['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$lnkExportToCSV'
form_data['__EVENTARGUMENT'] = ''

# Step 2: POST back to the same URL or form action
post_url = requests.compat.urljoin(URL, form.get("action", URL))
headers = {'Content-Type': 'application/x-www-form-urlencoded'}

r2 = session.post(post_url, data=form_data, headers=headers)

# Step 3: Save file
with open("output.csv", "wb") as f:
    f.write(r2.content)
