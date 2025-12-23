import os
import re
import random
import string
import requests
from datetime import datetime
import threading
import concurrent.futures
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


http_proxies = 'https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/http.txt'
https_proxies = 'https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/https.txt'

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def load_proxies():
    proxies = []
    try:
        response = requests.get(http_proxies)
        proxies.extend([line.strip() for line in response.text.splitlines() if line.strip()])
    except Exception as e:
        print(f"[!] Failed to load HTTP proxies: {e}")
    try:
        response = requests.get(https_proxies)
        proxies.extend([line.strip() for line in response.text.splitlines() if line.strip()])
    except Exception as e:
        print(f"[!] Failed to load HTTPS proxies: {e}")
    return list(set(proxies))

def check_proxy(proxy):
    try:
        response = requests.get('http://httpbin.org/ip', proxies={'http': proxy, 'https': proxy}, timeout=5)
        return response.status_code == 200
    except:
        return False

def extractCsrftoken(session):
    requestUrl = 'https://www.instagram.com/'
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Accept': 'text/html',
    })
    response = session.get(requestUrl)

    if response.status_code != 200:
        raise Exception(f"{RED}[!] Failed to load Instagram homepage. Status code: {response.status_code}{RESET}")

    # Try to get CSRF from HTML
    pattern = r'"csrf_token":"(.*?)"'
    match = re.search(pattern, response.text)

    if match:
        token = match.group(1)
        print(f"{GREEN}[+] CSRF token extracted: {token}{RESET}")
        return token

    # Try from cookies as fallback
    token = session.cookies.get('csrftoken')
    if token:
        print(f"{GREEN}[+] CSRF token from cookies: {token}{RESET}")
        return token

    raise Exception(f"{RED}[!] CSRF token could not be found.{RESET}")

def checkUsernameAvailability(session, username, csrftoken, proxies):
    url = 'https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/'

    session.headers.update({
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': csrftoken,
        'Referer': 'https://www.instagram.com/accounts/emailsignup/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Origin': 'https://www.instagram.com'
    })

    fake_email = ''.join(random.choices(string.ascii_lowercase, k=12)) + "@gmail.com"
    fake_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    fake_name = ''.join(random.choices(string.ascii_lowercase, k=8))

    payload = {
        'enc_password': f"#PWD_INSTAGRAM_BROWSER:0:{int(datetime.now().timestamp())}:{fake_password}",
        'email': fake_email,
        'username': username,
        'first_name': fake_name,
        'opt_into_one_tap': 'false'
    }

    proxy = random.choice(proxies) if proxies else None

    response = session.post(url, data=payload, proxies={"http": proxy, "https": proxy} if proxy else None)

    try:
        result = response.json()
    except Exception as e:
        print(f"{YELLOW}[!] Failed to parse response: {e}{RESET}")
        print(f"{YELLOW}{response.text}{RESET}")
        return None

    return result

def load_and_check_proxies():
    global working_proxies
    all_proxies = load_proxies()
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check_proxy, proxy): proxy for proxy in all_proxies}
        working_proxies = [futures[future] for future in futures if future.result()]
    print(f"✅ Found {len(working_proxies)} working proxies out of {len(all_proxies)}")

# ==== MAIN ====
session = requests.session()
csrftoken = extractCsrftoken(session)

working_proxies = []
use_proxies = input("Use proxies? (y/n): ").strip().lower() == 'y'
if use_proxies:
    print("🔍 Loading and checking proxies in background...")
    threading.Thread(target=load_and_check_proxies).start()
else:
    working_proxies = []

while True:
    username = input("Enter username (-1 to quit): ").strip()
    if username == '-1':
        break
    if not username:
        continue

    result = checkUsernameAvailability(session, username, csrftoken, working_proxies if use_proxies else [])

    if not result:
        print(f"{YELLOW}[!] No response or invalid data.{RESET}")
        continue

    # Check known error structure
    if 'errors' in result and 'username' in result['errors']:
        msg = result['errors']['username'][0].get('code', 'unavailable').replace('_', ' ')
        print(f"{RED}[-] Username '{username}' is taken or invalid: {msg}{RESET}")
    elif result.get("account_created") is False and "dryrun_passed" in result and result["dryrun_passed"]:
        print(f"{GREEN}[+] Username '{username}' is available.{RESET}")
    else:
        print(f"{YELLOW}[?] Unclear response for '{username}': {result}{RESET}")
