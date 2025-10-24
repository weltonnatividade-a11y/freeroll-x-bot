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

# Mapa de sites: lang ('en' ou 'pt'), affiliate link
SITE_MAP = {
    'unibetpoker': ('en', 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'),
    '888poker': ('pt', 'https://ic.aff-handler.com/c/48566?sr=1068421'),
    'coinpoker': ('pt', 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'),
    'redstar': ('en', ''),  # Sem afiliado específico, use genérico
    'pokerstars': ('en', ''),  # Adicione se tiver
    'wpt': ('pt', 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'),
    # Adicione mais conforme scrape
}

# Headers
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def parse_time_to_dt(time_str):
    """Melhorado: '13 minutes to start' ou '08:00 CET' -> dt UTC."""
    now = datetime.now(timezone.utc)
    time_str_lower = time_str.lower()
    if 'to start' in time_str_lower:
        mins_match = re.search(r'(\d+)\s*(minutes?|hours?)', time_str_lower)
        if mins_match:
            num = int(mins_match.group(1))
            unit = mins_match.group(2)
            delta = timedelta(minutes=num) if 'minute' in unit else timedelta(hours=num)
            return now + delta
    # HH:MM TZ
    match = re.match(r'(\d{2}):(\d{2})\s*(CET|ET|UTC)?', time_str.upper())
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        dt = datetime.combine(now.date(), datetime.min.time().replace(hour=h, minute=m))
        if match.group(3) == 'CET':
            dt = dt.replace(tzinfo=timezone.utc) + timedelta(hours=1)  # CET = UTC+1
        elif match.group(3) == 'ET':
            dt = dt.replace(tzinfo=timezone.utc) - timedelta(hours=4)  # ET = UTC-4
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
    table = soup.find('table', {'class': 'freeroll-table'})  # Seletor real
    if table:
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
        for row in rows[:10]:  # Top 10
            tds = row.find_all('td')
            if len(tds) >= 5:
                name_site = tds[0].get_text(strip=True).split('\n')
                site_name = name_site[0].lower().replace('poker', '') if name_site else 'unknown'
                time_str = tds[1].get_text(strip=True)
                prize = tds[4].get_text(strip=True)
                password = tds[3].get_text(strip=True) if tds[3].get_text(strip=True) != '—' else 'No password required'
                dt = parse_time_to_dt(time_str)
                if dt and now < dt <= now + timedelta(hours=24):
                    lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                    freerolls.append({
                        'name': name_site[1].strip() if len(name_site) > 1 else 'Freeroll',
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
    entries = soup.find_all('div', class_='freeroll-item')  # Ajuste baseado em checagem
    for entry in entries[:10]:
        time_elem = entry.find('span', class_='time')
        prize_elem = entry.find('span', class_='prize')
        pass_elem = entry.find('span', class_='password')
        site_elem = entry.find('span', class_='site') or entry.find('a', href=True)
        if time_elem:
            site_name = (site_elem.get_text(strip=True) if site_elem else 'wpt').lower()
            time_str = time_elem.get_text(strip=True)
            dt = parse_time_to_dt(time_str)
            if dt and now < dt <= now + timedelta(hours=24):
                lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                freerolls.append({
                    'name': entry.find('span', class_='name').get_text(strip=True) if entry.find('span', class_='name') else 'Freeroll',
                    'time': dt,
                    'site': site_name,
                    'prize': prize_elem.get_text(strip=True) if prize_elem else '',
                    'password': pass_elem.get_text(strip=True) if pass_elem and pass_elem.get_text(strip=True) != 'N/A' else 'No password required',
                    'lang': lang,
                    'link': aff_link
                })
    print(f"PokerFreerollPasswords: {len(freerolls)} freerolls encontrados")
    return freerolls

# Outros scrapes vazios hoje, pule ou adicione se mudar
def get_all_freerolls():
    global now
    now = datetime.now(timezone.utc)
    all_freerolls = scrape_pokerlistings() + scrape_pokerfreerollpasswords()
    upcoming = [f for f in all_freerolls if now < f['time'] <= now + timedelta(hours=24)]
    print(f"Total upcoming em 24h: {len(upcoming)}")
    return upcoming  # Agora posta todos os de hoje!

# Format tweet
def format_tweet(freerolls):
    if not freerolls:
        return None
    en_list, pt_list = [], []
    for f in freerolls[:5]:  # Top 5
        time_str = f['time'].strftime('%H:%M UTC')
        pw = f['password'] if f['password'] != 'No password required' else 'No password required'
        line = f"{f['name']} at {time_str} on {f['site'].title()} - Prize: {f['prize']} - PW: {pw} | Join: {f['link']}"
        if f['lang'] == 'pt':
            pt_line = f"{f['name']} às {time_str} no {f['site'].title()} - Prêmio: {f['prize']} - Senha: {pw} | Junte-se: {f['link']}"
            pt_list.append(pt_line)
        else:
            en_list.append(line)
    
    if en_list:
        return f"Today's Hot Freerolls! 🔥\n" + '\n'.join(en_list) + f"\n\nGrab free entries now! #PokerFreeroll #Freerolls"
    elif pt_list:
        return f"Freerolls quentes de hoje! 🔥\n" + '\n'.join(pt_list) + f"\n\nGaranta entradas grátis! #PokerFreeroll #Freerolls"
    return "Daily Freeroll Update: Check back soon! #Poker"

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
