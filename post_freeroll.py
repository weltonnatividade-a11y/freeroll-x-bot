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

# Mapa de sites: lang ('en' ou 'pt'), affiliate link (expandi com mais sites da lista)
SITE_MAP = {
    'coinpoker': ('pt', 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'),
    '888poker': ('pt', 'https://ic.aff-handler.com/c/48566?sr=1068421'),
    'unibetpoker': ('en', 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'),
    'redstar': ('en', ''),
    'pokerstars': ('en', ''),
    'wpt': ('pt', 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'),
    'wptglobal': ('pt', 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'),  # Alias
    # Adicione mais se scrape achar (ex.: tigergaming se aparecer)
}

# Headers
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def parse_time_to_dt(time_str):
    """Melhorado: '17 minutes to start' ou '08:00 CET' -> dt UTC."""
    now = datetime.now(timezone.utc)
    time_str_lower = time_str.lower()
    if 'to start' in time_str_lower:
        mins_match = re.search(r'(\d+)\s*(minutes?|hours?)', time_str_lower)
        if mins_match:
            num = int(mins_match.group(1))
            unit = mins_match.group(2)
            delta = timedelta(minutes=num) if 'minute' in unit else timedelta(hours=num)
            return now + delta
    # HH:MM TZ (simplificado)
    match = re.match(r'(\d{2}):(\d{2})\s*(CET|ET|UTC)?', time_str.upper())
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        dt = datetime.combine(now.date(), datetime.min.time().replace(hour=h, minute=m))
        if match.group(3) == 'CET':
            dt = dt.replace(tzinfo=timezone.utc) + timedelta(hours=1)  # CET=UTC+1
        elif match.group(3) == 'ET':
            dt = dt.replace(tzinfo=timezone.utc) - timedelta(hours=4)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt <= now:
            dt += timedelta(days=1)
        return dt
    return None

def scrape_pokerlistings():
    url = 'https://www.pokerlistings.com/free-rolls'
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    freerolls = []
    # Seletor melhorado: Procura tabela de freerolls (baseado em estrutura real: 'table' com 'tr' em 'div' ou 'tbody')
    tables = soup.find_all('table')  # Múltiplas tables; pega a com freerolls
    for table in tables:
        rows = table.find_all('tr')[:15]  # Top 15 pra cobrir
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 5:  # Colunas: site/name, time, ?, pw, prize
                full_text = tds[0].get_text(strip=True)
                if '\n' in full_text:
                    site_name = full_text.split('\n')[0].lower().replace('poker', '').strip()
                    name = full_text.split('\n', 1)[1].strip() if len(full_text.split('\n')) > 1 else 'Freeroll'
                else:
                    site_name = full_text.lower().replace('poker', '').strip()
                    name = 'Freeroll'
                time_str = tds[1].get_text(strip=True)
                prize = tds[4].get_text(strip=True)
                pw_text = tds[3].get_text(strip=True)
                password = pw_text if pw_text and pw_text != '—' else 'No password required'
                dt = parse_time_to_dt(time_str)
                if dt and now < dt <= now + timedelta(hours=24):
                    lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                    freerolls.append({
                        'name': name,
                        'time': dt,
                        'site': site_name,
                        'prize': prize,
                        'password': password,
                        'lang': lang,
                        'link': aff_link
                    })
    print(f"PokerListings: {len(freerolls)} freerolls encontrados")
    return freerolls

def scrape_pokerfreerollpasswords():
    url = 'https://pokerfreerollpasswords.com/#freerolls-today'
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    freerolls = []
    # Seletor melhorado: Procura divs com classes como 'entry', 'item' ou 'freeroll' (baseado em checagem)
    entries = soup.find_all(['div', 'li'], class_=re.compile(r'(freeroll|entry|item|today)'))[:15]
    for entry in entries:
        time_elem = entry.find(['span', 'div'], string=re.compile(r'\d{2}:\d{2}')) or entry.find(string=re.compile(r'ticket|prize'))
        if time_elem:
            time_str = time_elem.get_text(strip=True)
            site_elem = entry.find(['span', 'a', 'div'], string=re.compile(r'wpt|unknown', re.I)) or entry
            site_name = site_elem.get_text(strip=True).lower() if site_elem else 'wpt'
            prize_elem = entry.find(string=re.compile(r'\d+ ticket|€\d+|$\d+'))
            prize = prize_elem.get_text(strip=True) if prize_elem else ''
            pw_elem = entry.find(string=re.compile(r'pw|password', re.I))
            password = pw_elem.get_text(strip=True) if pw_elem else 'No password required'
            dt = parse_time_to_dt(time_str)
            if dt and now < dt <= now + timedelta(hours=24):
                lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                freerolls.append({
                    'name': entry.get_text(strip=True).split(time_str)[0].strip()[:50] or 'Freeroll',  # Nome genérico
                    'time': dt,
                    'site': site_name,
                    'prize': prize,
                    'password': password,
                    'lang': lang,
                    'link': aff_link
                })
    print(f"PokerFreerollPasswords: {len(freerolls)} freerolls encontrados")
    return freerolls

# Funções pros outros sites (ainda vazios, mas expandidas se precisar)
def scrape_thenuts():
    return []  # Nenhum hoje

def scrape_freerollpasswords():
    return []  # Nenhum

def scrape_raketherake():
    return []  # Nenhum

def scrape_freerollpass():
    return []  # Nenhum

def get_all_freerolls():
    global now
    now = datetime.now(timezone.utc)
    all_freerolls = (
        scrape_pokerlistings() + 
        scrape_pokerfreerollpasswords() + 
        scrape_thenuts() + 
        scrape_freerollpasswords() + 
        scrape_raketherake() + 
        scrape_freerollpass()
    )
    upcoming = [f for f in all_freerolls if now < f['time'] <= now + timedelta(hours=24)]
    print(f"Total upcoming em 24h: {len(upcoming)}")
    return upcoming

# Format tweet (limitado a 280 chars)
def format_tweet(freerolls):
    if not freerolls:
        return None
    lines = []
    for f in freerolls[:4]:  # Top 4 pra caber
        time_str = f['time'].strftime('%H:%M UTC')
        pw = f['password'][:20] + '...' if len(f['password']) > 20 else f['password']
        line = f"{f['name'][:30]}... @{time_str} {f['site'].title()} | {f['prize']} | PW: {pw} | {f['link']}"
        lines.append(line)
    en_or_pt = 'en' if any(l == 'en' for l in [f['lang'] for f in freerolls]) else 'pt'
    if en_or_pt == 'en':
        tweet = f"Today's Hot Freerolls! 🔥\n" + '\n'.join(lines) + f"\n\nGrab free entries! #PokerFreeroll"
    else:
        tweet = f"Freerolls quentes de hoje! 🔥\n" + '\n'.join(lines) + f"\n\nGaranta vagas grátis! #PokerFreeroll"
    return tweet[:280] + '...' if len(tweet) > 280 else tweet

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
