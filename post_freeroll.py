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

try:
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    print("Conexão com Twitter/X inicializada com sucesso")
except Exception as e:
    print(f"Erro ao inicializar tweepy.Client: {e}")

# Cabeçalhos para evitar 403
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# Sites (removido CardsChat, adicionado 888poker)
SITES = [
    "https://www.pokerlistings.com/free-rolls",
    "https://www.thenuts.com/freerolls",
    "https://freerollpasswords.com",
    "https://www.raketherake.com/poker/freerolls",
    "https://pokerfreerollpasswords.com",
    "https://www.888poker.com/poker-promotions/freerolls"
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

# Templates EN/PT
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

# Função para parsear data e horário do torneio
def parse_horario_torneio(data_str, hora_str=None, timezone_str="UTC"):
    try:
        data_str = data_str.strip()
        if hora_str:
            hora_str = hora_str.strip()
            data_hora_str = f"{data_str} {hora_str}"
            formatos = [
                "%Y-%m-%d %H:%M",  # Ex: 2025-10-24 14:30
                "%d/%m/%Y %H:%M",  # Ex: 24/10/2025 14:30
                "%Y/%m/%d %H:%M",  # Ex: 2025/10/24 14:30
                "%d-%m-%Y %H:%M"   # Ex: 24-10-2025 14:30
            ]
        else:
            data_hora_str = data_str
            formatos = [
                "%Y-%m-%d",  # Ex: 2025-10-24
                "%d/%m/%Y",  # Ex: 24/10/2025
                "%Y/%m/%d",  # Ex: 2025/10/24
                "%d-%m-%Y"   # Ex: 24-10-2025
            ]
        
        dt = None
        for fmt in formatos:
            try:
                dt = datetime.strptime(data_hora_str, fmt)
                break
            except ValueError:
                continue
        
        if not dt:
            raise ValueError(f"Formato de data/hora inválido: {data_hora_str}")
        
        timezone = zoneinfo.ZoneInfo(timezone_str)
        dt = dt.replace(tzinfo=timezone)
        dt_utc = dt.astimezone(zoneinfo.ZoneInfo("UTC"))
        return dt_utc
    except Exception as e:
        print(f"Erro ao parsear data/hora: {e}")
        return None

# Função para limpar URLs
def limpar_url(url):
    return url.strip().rstrip(":/")

# Função para obter freerolls
def obter_freerolls():
    freerolls = []
    for site in SITES:
        site = limpar_url(site)  # Limpa o URL
        print(f"Tentando acessar: {site}")
        try:
            response = requests.get(site, headers=HEADERS, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Ajuste os seletores para cada site
            if "pokerfreerollpasswords.com" in site:
                torneios = soup.find_all("div", class_="tournament-item") or soup.find_all("article")
            elif "888poker.com" in site:
                torneios = soup.find_all("div", class_=["tournament", "freeroll-event"])
            else:
                torneios = soup.find_all("tr", class_=["freeroll-row", "tournament-row", "event-row"]) or soup.find_all("div", class_=["freeroll", "tournament"])
            
            print(f"Torneios encontrados em {site}: {len(torneios)}")
            for torneio in torneios:
                try:
                    nome = torneio.find(["td", "div"], class_=["tournament-name", "name", "title"]) or torneio.find("h3") or torneio.find("h4")
                    nome = nome.text.strip() if nome else "Freeroll Sem Nome"
                    
                    sala = torneio.find(["td", "div"], class_=["site", "room", "poker-room"]) or torneio.find("span", class_="room")
                    sala = sala.text.strip().lower() if sala else None
                    sala = next((key for key in SITE_MAP if key in sala), None) if sala else None
                    
                    data = torneio.find(["td", "div"], class_=["date", "start-date"])
                    data = data.text.strip() if data else None
                    
                    hora = torneio.find(["td", "div"], class_=["time", "start-time"])
                    hora = hora.text.strip() if hora else None
                    
                    senha = torneio.find(["td", "div"], class_=["password", "pass"])
                    senha = senha.text.strip() if senha else "Sem senha"
                    
                    premio = torneio.find(["td", "div"], class_=["prize", "prizepool"])
                    premio = premio.text.strip() if premio else "Não informado"
                    
                    if sala and data:
                        data_hora = parse_horario_torneio(data, hora)
                        if data_hora and data_hora > datetime.now(zoneinfo.ZoneInfo("UTC")):
                            freerolls.append({
                                "nome": nome,
                                "sala": sala,
                                "data_hora": data_hora,
                                "senha": senha,
                                "premio": premio,
                                "link": SITE_MAP.get(sala, {}).get("link", LINK_FIXO),
                                "lang": SITE_MAP.get(sala, {}).get("lang", "en")
                            })
                            print(f"Freeroll adicionado: {nome} na {sala}")
                except Exception as e:
                    print(f"Erro ao processar torneio em {site}: {e}")
                    continue
        except Exception as e:
            print(f"Erro ao acessar {site}: {e}")
            continue
    return freerolls

# Função para criar o texto do post
def criar_texto_post(freeroll):
    templates = TEMPLATES_PT if freeroll["lang"] == "pt" else TEMPLATES_EN
    template = random.choice(templates)
    return template.format(
        sala=freeroll["sala"].capitalize(),
        senhas=freeroll["senha"],
        link=freeroll["link"]
    )

# Função principal para postar freerolls
def postar_freerolls():
    freerolls = obter_freerolls()
    if not freerolls:
        print("Nenhum freeroll encontrado.")
        return
    
    posted = 0
    for freeroll in freerolls:
        if posted >= 12:  # Limite de 12 posts por dia
            break
        texto = criar_texto_post(freeroll)
        try:
            client.create_tweet(text=texto)
            print(f"Postado: {texto}")
            with open("posts_log.txt", "a") as f:
                f.write(f"{datetime.now(zoneinfo.ZoneInfo('UTC'))}: {texto}\n")
            posted += 1
            time.sleep(7200)  # Intervalo de 2 horas entre posts
        except Exception as e:
            print(f"Erro ao postar: {e}")
            continue

# Executa o bot
if __name__ == "__main__":
    postar_freerolls()
