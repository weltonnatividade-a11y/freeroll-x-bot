import requests
from bs4 import BeautifulSoup
import tweepy
import os
from datetime import datetime, timedelta, timezone
import time
import re

# Chaves do X API (use secrets)
API_KEY = os.getenv('X_API_KEY')
API_SECRET = os.getenv('X_API_SECRET')
ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
ACCESS_SECRET = os.getenv('X_ACCESS_SECRET')

# Setup Tweepy
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# Mapa de sites: lang ('en' ou 'pt'), affiliate link (expandido com sites reais)
SITE_MAP = {
    'coinpoker': ('pt', 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'),
    '888poker': ('pt', 'https://ic.aff-handler.com/c/48566?sr=1068421'),
    'unibetpoker': ('en', 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'),
    'redstar': ('en', ''),
    'pokerstars': ('en', ''),
    'wpt': ('pt', 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'),
    'wptglobal': ('pt', 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'),
    # Adicione mais se precisar (ex.: 'tigergaming' se aparecer)
}

# Headers
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def parse_time_to_dt(time_str):
    """Parse '20 minutes to start' ou '06:02 CET' -> dt UTC."""
    now = datetime.now(timezone.utc)
    time_str_lower = time_str.lower().strip()
    # Relative time
    if 'to start' in time_str_lower:
        mins_match = re.search(r'(\d+)\s*(minutes?|hours?)\s*(\d+ minutes?)?', time_str_lower)
        if mins_match:
            num1 = int(mins_match.group(1))
            unit1 = mins_match.group(2)
            delta = timedelta(minutes=num1) if 'minute' in unit1 else timedelta(hours=num1)
            if mins_match.group(3):  # Ex: 1 hour 50 minutes
                num2 = int(re.search(r'(\d+)', mins_match.group(3)).group(1))
                delta += timedelta(minutes=num2)
            return now + delta
    # Absolute HH:MM TZ
    match = re.match(r'(\d{2}):(\d{2})\s*(CET|ET|UTC)?', time_str.upper())
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        today = now.date()
        dt = datetime.combine(today, datetime.min.time().replace(hour=h, minute=m))
        tz_offset = 0
        if match.group(3) == 'CET':
            tz_offset = 1  # CET = UTC+1
        elif match.group(3) == 'ET':
            tz_offset = -4
        dt = dt.replace(tzinfo=timezone.utc) + timedelta(hours=tz_offset)
        if dt <= now:
            dt += timedelta(days=1)
        return dt
    return None

def scrape_pokerlistings():
    url = 'https://www.pokerlistings.com/free-rolls'
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    freerolls = []
    # Seletor robusto: Qualquer table, filtra rows com >=5 tds e tempo relativo
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')[:20]  # Limite pra performance
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 5:
                full_site_text = tds[0].get_text(strip=True)
                site_match = re.search(r'(coinpoker|888poker|redstar|unibetpoker|pokerstars)', full_site_text.lower())
                site_name = site_match.group(1) if site_match else full_site_text.split('\n')[0].lower().replace('poker', '').strip()
                name = full_site_text.split('\n', 1)[1].strip() if '\n' in full_site_text else 'Freeroll'
                time_str = tds[1].get_text(strip=True)
                if 'to start' not in time_str and not re.match(r'\d{2}:\d{2}', time_str):
                    continue  # Pula se não for tempo válido
                prize = tds[4].get_text(strip=True)
                pw_text = tds[3].get_text(strip=True)
                password = pw_text if pw_text and pw_text != '—' and pw_text != '' else 'No password required'
                dt = parse_time_to_dt(time_str)
                if dt and now < dt <= now + timedelta(hours=24):
                    lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                    freeroll = {
                        'name': name,
                        'time': dt,
                        'site': site_name,
                        'prize': prize,
                        'password': password,
                        'lang': lang,
                        'link': aff_link
                    }
                    freerolls.append(free_roll)
                    print(f"  - {name} on {site_name} at {dt.strftime('%H:%M UTC')}")  # Debug
    print(f"PokerListings: {len(freerolls)} freerolls encontrados")
    return freerolls

def scrape_pokerfreerollpasswords():
    url = 'https://pokerfreerollpasswords.com/#freerolls-today'
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    freerolls = []
    # Seletor robusto: Blocos de texto com regex pra tempo e prize (markdown-like)
    text_blocks = soup.get_text(separator='\n').split('\n\n')  # Separa entradas
    for block in text_blocks[:20]:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) < 3:
            continue
        time_match = re.search(r'(\d{2}:\d{2})\s*(CET|ET)?', ' '.join(lines))
        if not time_match:
            continue
        time_str = time_match.group(0)
        site_match = re.search(r'(wpt|unknown)', ' '.join(lines), re.I)
        site_name = site_match.group(1).lower() if site_match else 'wpt'
        prize_match = re.search(r'(\d+ Tickets|€\d+|$\d+|\d+ prize pool)', ' '.join(lines))
        prize = prize_match.group(1) if prize_match else ''
        pw_match = re.search(r'Password:\s*(.+)', ' '.join(lines), re.I)
        password = pw_match.group(1) if pw_match else 'No password required'
        dt = parse_time_to_dt(time_str)
        if dt and now < dt <= now + timedelta(hours=24):
            name = lines[0] if lines else 'Freeroll'  # Genérico se "NAME"
            lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
            freeroll = {
                'name': name,
                'time': dt,
                'site': site_name,
                'prize': prize,
                'password': password,
                'lang': lang,
                'link': aff_link
            }
            freerolls.append(free_roll)
            print(f"  - {name} on {site_name} at {dt.strftime('%H:%M UTC')}")  # Debug
    print(f"PokerFreerollPasswords: {len(freerolls)} freerolls encontrados")
    return freerolls

# Outros sites (ainda sem dados consistentes, mas prontos)
def scrape_other_sites():
    return []

def get_all_freerolls():
    global now
    now = datetime.now(timezone.utc)
    all_freerolls = scrape_pokerlistings() + scrape_pokerfreerollpasswords() + scrape_other_sites()
    upcoming = [f for f in all_freerolls if now < f['time'] <= now + timedelta(hours=24)]
    print(f"Total upcoming em 24h: {len(upcoming)}")
    return upcoming

# Format tweet (corta pra 280 chars)
def format_tweet(freerolls):
    if not freerolls:
        return None
    lines = []
    for f in freerolls[:4]:  # Top 4
        time_str = f['time'].strftime('%H:%M UTC')
        pw_short = f['password'][:15] + '...' if len(f['password']) > 15 else f['password']
        line = f"{f['name'][:25]}... @{time_str} {f['site'].title()} | {f['prize']} | PW: {pw_short}"
        if f['link']:
            line += f" {f['link']}"
        lines.append(line)
    # Detecta lang dominante
    pt_count = sum(1 for f in freerolls if f['lang'] == 'pt')
    if pt_count > len(freerolls) / 2:
        tweet = f"Freerolls quentes de hoje! 🔥\n" + '\n'.join(lines) + f"\n\nGaranta vagas grátis! #PokerFreeroll"
    else:
        tweet = f"Today's Hot Freerolls! 🔥\n" + '\n'.join(lines) + f"\n\nGrab free entries! #PokerFreeroll"
    return tweet[:277] + '...' if len(tweet) > 280 else tweet  # Margem pros links

# Post
def post_tweet():
    freerolls = get_all_freerolls()
    tweet = format_tweet(freerolls)
    if tweet:
        try:
            api.update_status(tweet)
            print("Tweet postado com sucesso!")
        except Exception as e:
            print(f"Erro no post: {e}")
    else:
        print("No freerolls to post today.")

if __name__ == "__main__":
    post_tweet()
