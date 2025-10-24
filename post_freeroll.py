import os
import tweepy
import requests
from bs4 import BeautifulSoup
import random
import time
import re
from datetime import datetime, timedelta
import zoneinfo
import json

# Chaves do X (secrets: TWITTER_API_KEY etc.)
api_key = os.getenv('TWITTER_API_KEY')
api_secret = os.getenv('TWITTER_API_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

client = tweepy.Client(
    consumer_key=api_key,
    consumer_secret=api_secret,
    access_token=access_token,
    access_token_secret=access_token_secret
)

# Sites
SITES = [
    "https://www.pokerlistings.com/free-rolls",
    "https://freerollpass.com/pt",
    "https://www.thenuts.com/freerolls/",
    "https://freerollpasswords.com/",
    "https://www.raketherake.com/poker/freerolls",
    "https://pokerfreerollpasswords.com/#freerolls-today"
]

# Salas e afiliados (URLs completas)
SITE_MAP = {
    'coinpoker': {'lang': 'pt', 'link': 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'},
    '888poker': {'lang': 'pt', 'link': 'https://ic.aff-handler.com/c/48566?sr=1068421'},
    'unibetpoker': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'},
    'redstar': {'lang': 'en', 'link': ''},
    'wpt': {'lang': 'pt', 'link': 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'},
    'betsson': {'lang': 'pt', 'link': ''},
    'pokerstars': {'lang': 'en', 'link': ''},
    'americas cardroom': {'lang': 'en', 'link': 'https://record.secure.acraffiliates.com/_X7ahir7C9MEyEFx8EHG6c2Nd7ZgqdRLk/146/'},
    'partypoker': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78383?type=1'},
    'betonline': {'lang': 'pt', 'link': 'https://record.betonlineaffiliates.ag/_uPhqzdPJjdaIPOZC7y3OxGNd7ZgqdRLk/1/'},
}

# Templates EN/PT (limpos)
TEMPLATES_EN = [
    "Upcoming freeroll on {sala}! PW: {senhas}. Starts soon - win real prizes free! ♠️ {link}",
    "Alert! Freeroll on {sala} incoming. Use: {senhas} & build your bankroll. Ready? #PokerFreeroll",
    "Next freeroll on {sala}: exclusive PWs {senhas}. Rush to the tourney! {link}",
    "Hey poker fans! Freeroll on {sala} with PWs: {senhas}. No cost, pure skill! 💰",
    "Freeroll alert on {sala}: {senhas} - Hot event with prizes. #PokerFreeroll {link}"
]

TEMPLATES_PT = [
    "Freeroll futuro na {sala}! Senha: {senhas}. Início em breve - ganhe prêmios reais grátis! ♠️ {link}",
    "Alerta! Freeroll na {sala} rolando logo. Use: {senhas} e monte seu bankroll. Topa o desafio? #PokerGratis",
    "Próximo freeroll na {sala}: senhas exclusivas {senhas}. Corre pro torneio e dispute! {link}",
    "Ei, poker lovers! Freeroll na {sala} com senhas: {senhas}. Sem custo, só skill! 💰",
    "Freeroll alert na {sala}: {senhas} - Evento futuro bombando prêmios. #PokerFreeroll {link}"
]

LINK_FIXO = "https://linkr.bio/pokersenha"

def parse_horario_torneio(data_str, hora_str=None, timezone='UTC'):
    agora = datetime.now(zoneinfo.ZoneInfo(timezone))
    if hora_str and 'to start' in hora_str.lower():
        time_lower = hora_str.lower()
        hours_match = re.search(r'(\d+)\s*hour', time_lower)
        mins_match = re.search(r'(\d+)\s*minute', time_lower)
        hours = int(hours_match.group(1)) if hours_match else 0
        mins = int(mins_match.group(1)) if mins_match else 0
        return agora + timedelta(hours=hours, minutes=mins)
    # Absolute fallback
    try:
        for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d']:
            try:
                data = datetime.strptime(data_str, fmt)
                if hora_str and ':' in hora_str:
                    h, m = map(int, re.split(r'[^\d]', hora_str)[:2])
                    data = data.replace(hour=h, minute=m)
                return data.replace(tzinfo=zoneinfo.ZoneInfo(timezone))
            except:
                continue
    except:
        pass
    return None

def is_torneio_postavel(data_str, hora_str=None, timezone='UTC'):
    agora = datetime.now(zoneinfo.ZoneInfo(timezone))
    horario = parse_horario_torneio(data_str, hora_str, timezone)
    if not horario:
        return False
    diff_min = (horario - agora).total_seconds() / 60
    return diff_min > 0 and diff_min <= 1440  # 24h, não iniciado

def parse_pokerlistings(soup):
    eventos = []
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')[1:][:30]  # Skip header
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 4:  # Fix: >=4, pois prize é tds[3]
                full_brand = tds[0].get_text(strip=True)
                # Split por | pra time e brand
                parts = full_brand.split('|')
                if len(parts) >= 2:
                    time_str = parts[0].strip()
                    site_part = parts[1].strip()
                    # Split por <br> pra site e name
                    site_lines = site_part.split('<br>')
                    site_name = site_lines[0].lower().replace('poker', '').strip()
                    name = site_lines[1].strip() if len(site_lines) > 1 else 'Freeroll'
                else:
                    time_str = tds[1].get_text(strip=True)
                    site_name = full_brand.lower().replace('poker', '').strip()
                    name = 'Freeroll'
                prize = tds[3].get_text(strip=True).replace('prize: ', '').strip()  # Fix: tds[3] prize
                pw_text = tds[2].get_text(strip=True).strip()  # Fix: tds[2] password
                senha = pw_text if pw_text and pw_text not in ['—', 'none', ''] else 'No password required'
                if 'to start' in time_str.lower() and is_torneio_postavel('hoje', time_str):
                    eventos.append({'sala': site_name, 'senha': senha, 'data': 'hoje', 'hora': time_str, 'prize': prize, 'name': name})
                    print(f"  - {name} on {site_name}: {time_str}, {prize}, {senha}")
    print(f"PokerListings: {len(eventos)} encontrados")
    return eventos

def parse_thenuts(soup):
    eventos = []
    texto = soup.get_text().lower()
    for sala in SITE_MAP:
        if sala in texto:
            senha_match = re.search(r'{sala}.*?password[:\s]*([A-Z0-9]{{4,}}|no password)'.format(sala=sala), texto, re.IGNORECASE | re.DOTALL)
            senha = senha_match.group(1) if senha_match else 'No password required'
            time_match = re.search(r'{sala}.*?time et[:\s]*(\d{{1,2}}:\d{{2}}\s*(am|pm)?)'.format(sala=sala), texto, re.IGNORECASE | re.DOTALL)
            if time_match and is_torneio_postavel('hoje', time_match.group(1), 'US/Eastern'):
                eventos.append({'sala': sala, 'senha': senha, 'data': 'hoje', 'hora': time_match.group(1)})
    print(f"Thenuts: {len(eventos)} encontrados")
    return eventos

def parse_freerollpass(soup):
    eventos, agendamentos = [], []
    tabelas = soup.find_all('table')
    for tabela in tabelas:
        rows = tabela.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 3:
                sala = cols[0].get_text(strip=True).lower()
                if not any(k in sala for k in SITE_MAP):
                    continue
                hora = cols[1].get_text(strip=True)
                senha_col = cols[2].get_text(strip=True).lower()
                senha = re.search(r'([A-Z0-9]{4,})', senha_col)
                senha = senha.group(1) if senha else 'No password required'
                horario_disp = re.search(r'(disponível|available).*?(\d{1,2}:\d{2})', senha_col, re.IGNORECASE)
                if is_torneio_postavel('hoje', hora):
                    eventos.append({'sala': sala, 'senha': senha, 'data': 'hoje', 'hora': hora})
                elif horario_disp and is_torneio_postavel('hoje', hora):
                    agendamentos.append({'sala': sala, 'horario_senha': horario_disp.group(2), 'data_torneio': 'hoje', 'hora_torneio': hora, 'url': 'https://freerollpass.com/pt'})
    print(f"FreerollPass: {len(eventos)} encontrados")
    return eventos, agendamentos

def parse_raketherake(soup):
    eventos, agendamentos = [], []
    texto = soup.get_text().lower()
    for sala in SITE_MAP:
        if sala in texto:
            senha_match = re.search(r'{sala}.*?password[:\s]*([A-Z0-9]{{4,10}}|no password)'.format(sala=sala), texto, re.IGNORECASE | re.DOTALL)
            senha = senha_match.group(1) if senha_match else 'No password required'
            horario_match = re.search(r'{...
