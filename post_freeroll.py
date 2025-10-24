import os
import tweepy
import requests
from bs4 import BeautifulSoup
import random
import time
import re
from datetime import datetime, timedelta
import zoneinfo
import json  # Pra salvar estado diário

# Chaves do X (use secrets: TWITTER_API_KEY etc.)
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

# Sites (seus + PokerListings)
SITES = [
    "https://www.pokerlistings.com/free-rolls",
    "https://freerollpass.com/pt",
    "https://www.thenuts.com/freerolls/",
    "https://freerollpasswords.com/",
    "https://www.raketherake.com/poker/freerolls",
    "https://pokerfreerollpasswords.com/#freerolls-today"
]

# Salas e afiliados (expandido com lang)
SITE_MAP = {
    'coinpoker': {'lang': 'pt', 'link': 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'},
    '888poker': {'lang': 'pt', 'link': 'https://ic.aff-handler.com/c/48566?sr=1068421'},
    'unibetpoker': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'},
    'redstar': {'lang': 'en', 'link': ''},
    'wpt': {'lang': 'pt', 'link': 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'},
    'betsson': {'lang': 'pt', 'link': ''},  # Adicione se tiver
    'pokerstars': {'lang': 'en', 'link': ''},
    # Mais dos seus: americas cardroom etc.
    'americas cardroom': {'lang': 'en', 'link': 'https://record.secure.acraffiliates.com/_X7ahir7C9MEyEFx8EHG6c2Nd7ZgqdRLk/146/'},
    'partypoker': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78383?type=1'},
    'betonline': {'lang': 'pt', 'link': 'https://record.betonlineaffiliates.ag/_uPhqzdPJjdaIPOZC7y3OxGNd7ZgqdRLk/1/'},
}

# Templates EN/PT (seus, adaptados)
TEMPLATES_EN = [
    "🚀 Upcoming freeroll on {sala}! PW: {senhas}. Starts soon – win real prizes free! ♠️ {link}",
    "Alert! Freeroll on {sala} incoming. Use: {senhas} & build your bankroll. Ready?",
    "Next freeroll on {sala}: exclusive PWs {senhas}. Rush to the tourney!",
    "Hey poker fans! Freeroll on {sala} with PWs: {senhas}. No cost, pure skill! 💰",
    "Freeroll alert on {sala}: {senhas} – Hot event with prizes. #PokerFreeroll {link}"
]

TEMPLATES_PT = [
    "🚀 Freeroll futuro na {sala}! Senha: {senhas}. Início em breve – ganhe prêmios reais grátis! ♠️ {link}",
    "Alerta! Freeroll na {sala} rolando logo. Use: {senhas} e monte seu bankroll. Topa o desafio?",
    "Próximo freeroll na {sala}: senhas exclusivas {senhas}. Corre pro torneio e dispute!",
    "Ei, poker lovers! Freeroll na {sala} com senhas: {senhas}. Sem custo, só skill! 💰",
    "Freeroll alert na {sala}: {senhas} – Evento futuro bombando prêmios. #PokerGratis {link}"
]

LINK_FIXO = "https://linkr.bio/pokersenha"

# Seus parsers (ajustados com dados reais)
def parse_horario_torneio(data_str, hora_str=None, timezone='UTC'):
    try:
        for fmt in ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d']:
            try:
                data = datetime.strptime(data_str, fmt)
                if hora_str:
                    hora_limpa = re.sub(r'[^\d:\sAMPM]', '', hora_str)
                    data = datetime.strptime(f"{data_str} {hora_limpa}", f"{fmt} %I:%M %p") if 'AM' in hora_limpa.upper() or 'PM' in hora_limpa.upper() else data.replace(hour=int(hora_str.split(':')[0]), minute=int(hora_str.split(':')[1].split()[0]) if ':' in hora_str else 0)
                return data
            except:
                continue
    except:
        pass
    return None

def is_torneio_postavel(data_str, hora_str=None, timezone='UTC'):
    agora = datetime.now(zoneinfo.ZoneInfo(timezone))
    hoje = agora.date()
    horario = parse_horario_torneio(data_str, hora_str, timezone)
    if not horario or horario.date() != hoje:
        return False
    diff_min = (horario - agora).total_seconds() / 60
    return diff_min > 0  # Não iniciado (ajuste pra > -5 se quiser 5 min antes max)

# Parser PokerListings (novo, baseado em dados reais)
def parse_pokerlistings(soup):
    eventos = []
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')[:20]
        for row in rows:
            tds = row.find_all('td')
            if len(tds) >= 5:
                full_site = tds[0].get_text(strip=True).lower()
                site_name = next((k for k in SITE_MAP if k in full_site), full_site.split('\n')[0].strip())
                time_str = tds[1].get_text(strip=True)
                prize = tds[4].get_text(strip=True)
                pw_text = tds[3].get_text(strip=True)
                senha = pw_text if pw_text != '—' and pw_text != 'none' else 'No password required'
                if is_torneio_postavel('hoje', time_str):  # Usa time_str como hora
                    eventos.append({'sala': site_name, 'senha': senha, 'data': 'hoje', 'hora': time_str, 'prize': prize})
    return eventos

# Seus parsers (mantidos/ajustados)
def parse_thenuts(soup):
    # Seu código, ajustado pra dados vazios hoje
    eventos = []
    texto = soup.get_text().lower()
    for sala in SITE_MAP:
        if sala in texto:
            senha_match = re.search(rf'{sala}.*?password[:\s]*([A-Z0-9]{{4,}})', texto, re.IGNORECASE | re.DOTALL)
            time_match = re.search(rf'{sala}.*?time et[:\s]*(\d{{1,2}}:\d{{2}}\s*(am|pm)?)', texto, re.IGNORECASE | re.DOTALL)
            if senha_match and time_match and is_torneio_postavel('hoje', time_match.group(1), 'US/Eastern'):
                eventos.append({'sala': sala, 'senha': senha_match.group(1), 'data': 'hoje', 'hora': time_match.group(1)})
    return eventos

def parse_freerollpass(soup):
    # Seu código, com regex pra release
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
                senha_col = cols[2].get_text(strip=True)
                senha = re.search(r'([A-Z0-9]{4,})', senha_col)
                horario_disp = re.search(r'(disponível|available).*?(\d{1,2}:\d{2})', senha_col, re.IGNORECASE)
                if senha and is_torneio_postavel('hoje', hora):
                    eventos.append({'sala': sala, 'senha': senha.group(1), 'data': 'hoje', 'hora': hora})
                elif horario_disp and is_torneio_postavel('hoje', hora):
                    agendamentos.append({'sala': sala, 'horario_senha': horario_disp.group(2), 'data_torneio': 'hoje', 'hora_torneio': hora, 'url': 'https://freerollpass.com/pt'})
    return eventos, agendamentos

def parse_raketherake(soup):
    # Seu código
    eventos, agendamentos = [], []
    texto = soup.get_text().lower()
    for sala in SITE_MAP:
        if sala in texto:
            senha_match = re.search(rf'{sala}.*?password[:\s]*([A-Z0-9]{{4,10}})', texto, re.IGNORECASE | re.DOTALL)
            horario_match = re.search(rf'{sala}.*?(password available|senha disponível).*?(\d{{1,2}}:\d{{2}})', texto, re.IGNORECASE | re.DOTALL)
            if senha_match:
                eventos.append({'sala': sala, 'senha': senha_match.group(1), 'data': 'hoje'})
            elif horario_match:
                agendamentos.append({'sala': sala, 'horario_senha': horario_match.group(2), 'url': 'https://www.raketherake.com/poker/freerolls'})
    return eventos, agendamentos

def parse_generic(soup, url):
    # Seu genérico + PokerFreerollPasswords
    eventos = []
    texto = soup.get_text().lower()
    for sala in SITE_MAP:
        if sala in texto:
            padroes_senha = re.findall(r'(?:password|senha|pw)[:\s]*([A-Z0-9]{4,10})', texto, re.IGNORECASE)
            padroes_tempo = re.findall(r'(\d{2}:\d{2}\s*(CET|ET)?)', texto)
            for senha in padroes_senha:
                for tempo in padroes_tempo:
                    if is_torneio_postavel('hoje', tempo[0]):
                        eventos.append({'sala': sala, 'senha': senha, 'data': 'hoje', 'hora': tempo[0]})
                        break
    return eventos, []

def buscar_senhas():
    eventos, agendamentos = [], []
    for url in random.sample(SITES, min(4, len(SITES))):
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            if 'pokerlistings' in url:
                eventos.extend(parse_pokerlistings(soup))
            elif 'thenuts' in url:
                eventos.extend(parse_thenuts(soup))
            elif 'freerollpass' in url:
                evs, ags = parse_freerollpass(soup)
                eventos.extend(evs)
                agendamentos.extend(ags)
            elif 'raketherake' in url:
                evs, ags = parse_raketherake(soup)
                eventos.extend(evs)
                agendamentos.extend(ags)
            else:
                evs, ags = parse_generic(soup, url)
                eventos.extend(evs)
                agendamentos.extend(ags)
        except Exception as e:
            print(f"Erro em {url}: {e}")
    # Dedup
    seen = set()
    unique = [ev for ev in eventos if (ev['senha'], ev['sala']) not in seen and is_torneio_postavel(ev.get('data', 'hoje'), ev.get('hora', '')) and seen.add((ev['senha'], ev['sala']))]
    return unique[:5], agendamentos

# Seu buscar_senha_agendada (com 4 min sleep)
def buscar_senha_agendada(url, sala):
    for tentativa in range(2):
        try:
            print(f"Tentativa {tentativa+1}: Senha pra {sala} em {url}")
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            texto = soup.get_text()
            senha_match = re.search(rf'{sala}.*?(?:password|senha)[:\s]*([A-Z0-9]{{4,10}})', texto, re.IGNORECASE | re.DOTALL)
            if senha_match:
                print(f"Senha encontrada: {senha_match.group(1)}")
                return {'sala': sala, 'senha': senha_match.group(1), 'data': 'hoje'}
            if tentativa == 0:
                time.sleep(240)  # 4 min
        except Exception as e:
            print(f"Erro agendada: {e}")
            if tentativa == 0:
                time.sleep(240)
    return None

def processar_agendamentos(agendamentos):
    agora = datetime.now()
    for ag in agendamentos:
        hora_match = re.match(r'(\d{1,2}):(\d{2})', ag['horario_senha'])
        if hora_match:
            hora_senha = agora.replace(hour=int(hora_match.group(1)), minute=int(hora_match.group(2)))
            diff = (agora - hora_senha).total_seconds()
            if -300 <= diff <= 300:  # ±5 min
                print(f"Horário senha pra {ag['sala']}!")
                return [buscar_senha_agendada(ag['url'], ag['sala'])]
    return []

# Seu gerar_post, adaptado pra lang/link
def gerar_post(eventos):
    if not eventos:
        return None
    ev = random.choice(eventos)
    sala_info = SITE_MAP.get(ev['sala'], {'lang': 'pt', 'link': ''})
    lang = sala_info['lang']
    link = f" {sala_info['link']}" if sala_info['link'] else ""
    templates = TEMPLATES_PT if lang == 'pt' else TEMPLATES_EN
    senhas_str = ev['senha']
    extras = [e['senha'] for e in random.sample(eventos, min(1, len(eventos)-1)) if e['sala'] != ev['sala']]
    if extras:
        senhas_str += f" and {', '.join(extras)}"
    if senhas_str == 'No password required':
        senhas_str = "No password required"
    template = random.choice(templates)
    msg = template.format(sala=ev['sala'].title(), senhas=senhas_str, link=link)
    msg += f"\n\n{LINK_FIXO}" if random.random() > 0.5 else "\n\nLink in bio! 📍"
    return msg[:280]

# Limites diários (salva em /tmp pra stateless Actions)
def load_state():
    try:
        with open('/tmp/bot_state.json', 'r') as f:
            return json.load(f)
    except:
        return {'posts_hoje': 0, 'ultimo_dia': str(datetime.now().date()), 'ultimo_post': 0}

def save_state(state):
    with open('/tmp/bot_state.json', 'w') as f:
        json.dump(state, f)

def post_tweet():
    state = load_state()
    hoje = str(datetime.now().date())
    if hoje != state['ultimo_dia']:
        state = {'posts_hoje': 0, 'ultimo_dia': hoje, 'ultimo_post': 0}
    if state['posts_hoje'] >= 4:
        print("Limite diário atingido.")
        return
    agora_ts = time.time()
    if agora_ts - state['ultimo_post'] < 3600:
        print("Intervalo de 1h não atingido.")
        return
    eventos, agend = buscar_senhas()
    eventos_agend = processar_agendamentos(agend)
    eventos.extend(eventos_agend)
    tweet = gerar_post(eventos)
    if tweet:
        try:
            response = client.create_tweet(text=tweet)
            state['posts_hoje'] += 1
            state['ultimo_post'] = agora_ts
            save_state(state)
            print(f"Postado! ID: {response.data['id']}\n{tweet}")
        except Exception as e:
            print(f"Erro post: {e}")
    else:
        print("Sem freerolls pra postar hoje.")

if __name__ == "__main__":
    post_tweet()
