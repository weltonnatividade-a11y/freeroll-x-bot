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
    'tigergaming': ('en', 'https://record.tigergamingaffiliates.com/_uPhqzdPJjdYiTPmoIIeY2mNd7ZgqdRLk/1/'),
    'americascardroom': ('en', 'https://record.secure.acraffiliates.com/_X7ahir7C9MEyEFx8EHG6c2Nd7ZgqdRLk/146/'),
    'stake': ('en', 'https://stake.bet/?c=TsaKFUEF'),
    'partypoker': ('en', 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78383?type=1'),
    'paddypower': ('en', 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78386?type=1'),
    'unibet': ('en', 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'),
    '888': ('pt', 'https://ic.aff-handler.com/c/48566?sr=1068421'),
    'coinpoker': ('pt', 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'),
    'betplay': ('pt', 'https://betplay.io?ref=b27df8088d31'),
    'betonline': ('pt', 'https://record.betonlineaffiliates.ag/_uPhqzdPJjdaIPOZC7y3OxGNd7ZgqdRLk/1/'),
    'wptpoker': ('pt', 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'),
    'highstakes': ('pt', 'https://highstakes.com/affiliate/weltonnatividade'),
    'jackpoker': ('pt', 'https://go.jack-full.com/go/e16f18cf'),
    'bodog': ('pt', 'https://record.revenuenetwork.com/_-53GkjkSe434SOPHpOpTwGNd7ZgqdRLk/1348/')
}

# Headers pra evitar block
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def parse_time_to_dt(time_str, site_tz='UTC'):
    """Parse time str to datetime UTC. Ex: '08:00 CET' -> dt, or '32 minutes to start' -> now + 32 min."""
    now = datetime.now(timezone.utc)
    if 'to start' in time_str:
        mins = re.search(r'(\d+) (minutes?|hours?)', time_str.lower())
        if mins:
            delta = timedelta(minutes=int(mins.group(1))) if 'minute' in mins.group(2) else timedelta(hours=int(mins.group(1)))
            return now + delta
        return now  # fallback
    # Para 'HH:MM TZ'
    match = re.match(r'(\d{2}):(\d{2})\s*(CET|ET|UTC)?', time_str.upper())
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        dt = datetime.combine(now.date(), datetime.min.time().replace(hour=h, minute=m))
        # Ajusta TZ se CET (-1h UTC? CET=UTC+1, mas simplificado)
        if match.group(3) == 'CET':
            dt -= timedelta(hours=1)  # Approx
        elif match.group(3) == 'ET':
            dt -= timedelta(hours=4)  # ET=UTC-4
        if dt < now:
            dt += timedelta(days=1)
        dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None  # Invalid

def scrape_pokerlistings():
    url = 'https://www.pokerlistings.com/free-rolls'
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    freerolls = []
    table = soup.find('table', class_='freeroll-table')
    if table:
        rows = table.find('tbody').find_all('tr')[:5]  # Top 5
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 5:
                site_name = tds[0].get_text(strip=True).split('\n')[0].lower()  # Ex: 888poker
                time_str = tds[1].get_text(strip=True)
                prize = tds[4].get_text(strip=True)
                password = tds[3].get_text(strip=True) if tds[3].get_text(strip=True) != '—' else 'No password required'
                dt = parse_time_to_dt(time_str)
                if dt and now < dt <= now + timedelta(hours=24):
                    lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                    freerolls.append({
                        'name': tds[0].get_text(strip=True).split('\n',1)[1].strip() if '\n' in tds[0].get_text() else 'Freeroll',
                        'time': dt,
                        'site': site_name,
                        'prize': prize,
                        'password': password,
                        'lang': lang,
                        'link': aff_link
                    })
    return freerolls

# Função similar pra outros sites (exemplo; adapte com seus seletores se mandar código)
def scrape_thenuts():
    url = 'https://www.thenuts.com/freerolls/'
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    freerolls = []
    entries = soup.find_all('div', class_='freeroll-entry')[:5]
    for entry in entries:
        site_elem = entry.find('h3', class_='site')
        time_elem = entry.find('span', class_='time')
        prize_elem = entry.find('span', class_='prize')
        pass_elem = entry.find('span', class_='password')
        if site_elem and time_elem:
            site_name = site_elem.get_text(strip=True).lower()
            time_str = time_elem.get_text(strip=True)
            dt = parse_time_to_dt(time_str, 'ET')
            if dt and now < dt <= now + timedelta(hours=24):
                lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                freerolls.append({
                    'name': entry.find('p', class_='tournament-name').get_text(strip=True) if entry.find('p', class_='tournament-name') else 'Freeroll',
                    'time': dt,
                    'site': site_name,
                    'prize': prize_elem.get_text(strip=True) if prize_elem else '',
                    'password': pass_elem.get_text(strip=True) if pass_elem else 'No password required',
                    'lang': lang,
                    'link': aff_link
                })
                # Check password release? Assume no field; add if parse 'release at HH:MM'
                release_match = re.search(r'release at (\d{2}:\d{2})', pass_elem.get_text() if pass_elem else '')
                if release_match and parse_time_to_dt(release_match.group(1)) > now:
                    time.sleep(240)  # 4 min
                    # Re-scrape this entry (simplificado; re-chame func se preciso)
    return freerolls

def scrape_pokerfreerollpasswords():
    url = 'https://pokerfreerollpasswords.com/'
    resp = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(resp.text, 'html.parser')
    freerolls = []
    section = soup.find('section', id='freerolls-today')
    if section:
        entries = section.find_all('div', class_='freeroll-entry')[:5]
        for entry in entries:
            time_elem = entry.find('span', class_='time')
            prize_elem = entry.find('span', class_='prize')
            pass_elem = entry.find('span', class_='password')
            site_link = entry.find('a', class_='site-link')['href'] if entry.find('a', class_='site-link') else ''
            site_name = site_link.split('/')[-2] if site_link else 'unknown'  # Infer from link
            if time_elem:
                time_str = time_elem.get_text(strip=True)
                dt = parse_time_to_dt(time_str, 'CET')
                if dt and now < dt <= now + timedelta(hours=24):
                    lang, aff_link = SITE_MAP.get(site_name, ('en', ''))
                    freerolls.append({
                        'name': entry.find('span', class_='name').get_text(strip=True) if entry.find('span', class_='name') else 'Freeroll',
                        'time': dt,
                        'site': site_name,
                        'prize': prize_elem.get_text(strip=True) if prize_elem else '',
                        'password': pass_elem.get_text(strip=True) if pass_elem else 'No password required',
                        'lang': lang,
                        'link': aff_link
                    })
    return freerolls

# Adicione funções pra outros sites similares (raketherake: table vazia hoje, skip; freerollpass: sem dados, skip; freerollpasswords: insuficiente)
def scrape_other_sites():  # Placeholder pra restantes
    return []  # Integre seu código aqui se tiver

# Main: Coleta todos
now = datetime.now(timezone.utc)
def get_all_freerolls():
    all_freerolls = []
    all_freerolls += scrape_pokerlistings()
    all_freerolls += scrape_thenuts()
    all_freerolls += scrape_pokerfreerollpasswords()
    all_freerolls += scrape_other_sites()  # Adicione mais
    # Filter: só dentro 24h, not started, and within 5 min before? Wait, post if any close
    upcoming = [f for f in all_freerolls if now < f['time'] <= now + timedelta(hours=24)]
    close_ones = [f for f in upcoming if f['time'] - now <= timedelta(minutes=5)]
    return upcoming if close_ones else []  # Post só se close

# Format tweet por lang
def format_tweet(freerolls):
    if not freerolls:
        return None
    # Group by lang
    en_list, pt_list = [], []
    for f in freerolls[:3]:  # Top 3
        line = f"{f['name']} at {f['time'].strftime('%H:%M')} on {f['site']} - Prize: {f['prize']} - PW: {f['password']} Join: {f['link']}"
        if f['lang'] == 'en':
            en_list.append(line)
        else:
            pt_line = f"{f['name']} às {f['time'].strftime('%H:%M')} no {f['site']} - Prêmio: {f['prize']} - Senha: {f['password']} Junte-se: {f['link']}"
            pt_list.append(pt_line)
    
    if en_list:
        tweet_en = f"Hot Freerolls today! 🔥\n" + '\n'.join(en_list) + "\nGrab seats now! #PokerFreeroll"
        return tweet_en  # Priorize EN; ou post 2 se quiser
    elif pt_list:
        tweet_pt = f"Freerolls quentes hoje! 🔥\n" + '\n'.join(pt_list) + "\nGaranta sua vaga! #PokerFreeroll"
        return tweet_pt
    return "Daily Freeroll Check: No hot ones right now. Stay tuned! #Poker"

# Post
def post_tweet():
    freerolls = get_all_freerolls()
    tweet = format_tweet(freerolls)
    if tweet:
        try:
            api.update_status(tweet)
            print("Tweet postado!")
        except Exception as e:
            print(f"Erro: {e}")
    else:
        print("No post needed - no close freerolls.")

if __name__ == "__main__":
    post_tweet()
