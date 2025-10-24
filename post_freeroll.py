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
import logging
from difflib import SequenceMatcher
import schedule

# Configuração de logging
logging.basicConfig(filename='bot_errors.log', level=logging.ERROR)

# Chaves do X
api_key = os.getenv('TWITTER_API_KEY')
api_secret = os.getenv('TWITTER_API_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

if not all([api_key, api_secret, access_token, access_token_secret]):
    raise ValueError("Uma ou mais variáveis de ambiente do Twitter/X não estão definidas")

client = tweepy.Client(
    consumer_key=api_key,
    consumer_secret=api_secret,
    access_token=access_token,
    access_token_secret=access_token_secret
)
print("Conexão com Twitter/X inicializada com sucesso")

# Cabeçalhos para requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# Sites para scraping
SITES = [
    "https://freerollpass.com/pt",
    "https://www.thenuts.com/freerolls",
    "https://freerollpasswords.com",
    "https://www.raketherake.com/poker/freerolls",
    "https://pokerfreerollpasswords.com/#freerolls-today",
    "https://www.pokerlistings.com/free-rolls"
]

# Mapeamento de salas e links de afiliados
SITE_MAP = {
    'tigergaming': {'lang': 'en', 'link': 'https://record.tigergamingaffiliates.com/_uPhqzdPJjdYiTPmoIIeY2mNd7ZgqdRLk/1/'},
    'acr poker': {'lang': 'en', 'link': 'https://record.secure.acraffiliates.com/_X7ahir7C9MEyEFx8EHG6c2Nd7ZgqdRLk/146/'},
    'americas cardroom': {'lang': 'en', 'link': 'https://record.secure.acraffiliates.com/_X7ahir7C9MEyEFx8EHG6c2Nd7ZgqdRLk/146/'},
    'stake': {'lang': 'en', 'link': 'https://stake.bet/?c=TsaKFUEF'},
    'partypoker': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78383?type=1'},
    'paddypower': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78386?type=1'},
    'unibet': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'},
    '888poker': {'lang': 'pt', 'link': 'https://ic.aff-handler.com/c/48566?sr=1068421'},
    'coinpoker': {'lang': 'pt', 'link': 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'},
    'betplay': {'lang': 'pt', 'link': 'https://betplay.io?ref=b27df8088d31'},
    'betonline': {'lang': 'pt', 'link': 'https://record.betonlineaffiliates.ag/_uPhqzdPJjdaIPOZC7y3OxGNd7ZgqdRLk/1/'},
    'wptpoker': {'lang': 'pt', 'link': 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'},
    'highstakes': {'lang': 'pt', 'link': 'https://highstakes.com/affiliate/weltonnatividade'},
    'jackpoker': {'lang': 'pt', 'link': 'https://go.jack-full.com/go/e16f18cf'},
    'bodog': {'lang': 'pt', 'link': 'https://record.revenuenetwork.com/_-53GkjkSe434SOPHpOpTwGNd7ZgqdRLk/1348/'}
}

# Templates de postagem
TEMPLATES_EN = [
    "Upcoming freeroll on {sala}! {senhas} Starts soon - win big! ♠️ {link} #PokerFreeroll",
    "Freeroll alert on {sala}! {senhas} Join now for free prizes! 💰 {link}",
    "Get ready for a freeroll on {sala}! {senhas} Don’t miss out! {link}"
]

TEMPLATES_PT = [
    "Freeroll na {sala}! {senhas} Começa em breve - ganhe prêmios grátis! ♠️ {link} #PokerGratis",
    "Alerta de freeroll na {sala}! {senhas} Entre agora e dispute! 💰 {link}",
    "Prepare-se para o freeroll na {sala}! {senhas} Não perca! {link}"
]

LINK_FIXO = "https://linkr.bio/pokersenha"

# Import opcional do Selenium
SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
    print("Selenium disponível - sites dinâmicos serão scraped com JS.")
except ImportError:
    print("Selenium não instalado. Usando fallback requests para sites dinâmicos (pode falhar em JS pesado). Instale com 'pip install selenium'.")

# Função para scraping dinâmico com Selenium (ou fallback)
def scrape_dynamic_site(url):
    if SELENIUM_AVAILABLE:
        options = Options()
        options.headless = True
        options.add_argument(f"user-agent={HEADERS['User-Agent']}")
        try:
            driver = webdriver.Chrome(options=options)
            driver.get(url)
            time.sleep(3)  # Espera carregar
            soup = BeautifulSoup(driver.page_source, "html.parser")
            driver.quit()
            return soup
        except Exception as e:
            logging.error(f"Erro ao acessar {url} com Selenium: {e}")
            print(f"Fallback para requests em {url}")
    # Fallback: requests simples
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        logging.error(f"Erro no fallback requests para {url}: {e}")
        return None

# Função para parsear data e horário
def parse_horario_torneio(data_str, hora_str=None, timezone_str="UTC"):
    try:
        data_str = data_str.strip()
        if "min" in data_str.lower() or "hour" in data_str.lower():
            minutes = int(re.search(r'\d+', data_str).group()) if re.search(r'\d+', data_str) else 0
            return datetime.now(zoneinfo.ZoneInfo("UTC")) + timedelta(minutes=minutes)
        if hora_str:
            hora_str = hora_str.strip()
            data_hora_str = f"{data_str} {hora_str}"
            formatos = [
                "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%Y/%m/%d %H:%M", "%d-%m-%Y %H:%M",
                "%B %d, %Y %I:%M %p"
            ]
        else:
            data_hora_str = data_str
            formatos = ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%B %d, %Y"]
        
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
        return dt.astimezone(zoneinfo.ZoneInfo("UTC"))
    except Exception as e:
        logging.error(f"Erro ao parsear data/hora: {e}")
        return None

# Função para limpar URLs
def limpar_url(url):
    return url.strip().rstrip(":/")

# Função para deduplicar freerolls
def deduplicate_freerolls(freerolls):
    unique_freerolls = []
    for freeroll in freerolls:
        is_duplicate = False
        for unique in unique_freerolls:
            if (freeroll["sala"] == unique["sala"] and 
                abs((freeroll["data_hora"] - unique["data_hora"]).total_seconds()) < 1800 and
                SequenceMatcher(None, freeroll["nome"], unique["nome"]).ratio() > 0.8):
                is_duplicate = True
                break
        if not is_duplicate:
            unique_freerolls.append(freeroll)
    return unique_freerolls

# Função para obter freerolls
def obter_freerolls():
    freerolls = []
    now = datetime.now(zoneinfo.ZoneInfo("UTC"))
    tomorrow = now + timedelta(hours=24)
    
    for site in SITES:
        site = limpar_url(site)
        print(f"Tentando acessar: {site}")
        try:
            # Usa Selenium para sites dinâmicos
            if "pokerfreerollpasswords.com" in site or "freerollpasswords.com" in site or "raketherake.com" in site:
                soup = scrape_dynamic_site(site)
            else:
                response = requests.get(site, headers=HEADERS, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
            
            if not soup:
                continue
            
            # Seletores específicos por site
            if "pokerlistings.com" in site:
                torneios = soup.find_all("tr", class_="freeroll-row")
            elif "thenuts.com" in site:
                torneios = soup.find_all("div", class_="tournament-block")
            elif "freerollpass.com" in site:
                torneios = soup.find_all("div", class_=["freeroll-item", "tournament"])
            elif "freerollpasswords.com" in site or "pokerfreerollpasswords.com" in site:
                torneios = soup.find_all("div", class_=["tournament-block", "freeroll"])
            elif "raketherake.com" in site:
                torneios = soup.find_all("div", class_=["freeroll", "promotion"])
            else:
                torneios = soup.find_all("tr", class_=["freeroll-row", "tournament-row"]) or soup.find_all("div", class_=["freeroll", "tournament"])
            
            print(f"Torneios encontrados em {site}: {len(torneios)}")
            for torneio in torneios:
                try:
                    nome = torneio.find(["td", "div", "h3", "h4"], class_=["tournament-name", "name", "title"]) or torneio.find("h3")
                    nome = nome.text.strip() if nome else "Freeroll Sem Nome"
                    
                    sala = torneio.find(["td", "div", "span"], class_=["site", "room", "poker-room"])
                    sala = sala.text.strip().lower() if sala else ""
                    sala = next((key for key in SITE_MAP if key in sala), None)
                    if not sala:
                        continue
                    
                    data = torneio.find(["td", "div"], class_=["date", "start-date"])
                    data = data.text.strip() if data else None
                    
                    hora = torneio.find(["td", "div"], class_=["time", "start-time"])
                    hora = hora.text.strip() if hora else None
                    
                    senha = torneio.find(["td", "div"], class_=["password", "pass"])
                    senha = senha.text.strip() if senha else "No password required"
                    
                    premio = torneio.find(["td", "div"], class_=["prize", "prizepool"])
                    premio = premio.text.strip() if premio else "Not informed"
                    
                    late_reg = torneio.find(["td", "div", "span"], class_=["late-registration", "late-reg"])
                    late_reg = "late registration" in (late_reg.text.lower() if late_reg else "")
                    
                    # Verificar horário de liberação de senha
                    senha_hora = torneio.find(["td", "div"], class_=["password-release", "release-time"])
                    senha_hora = parse_horario_torneio(senha_hora.text.strip()) if senha_hora else None
                    
                    if data:
                        data_hora = parse_horario_torneio(data, hora, "America/New_York" if "thenuts.com" in site else "UTC")
                        if data_hora and now <= data_hora <= tomorrow and (not data_hora < now or late_reg):
                            freeroll = {
                                "nome": nome,
                                "sala": sala,
                                "data_hora": data_hora,
                                "senha": senha,
                                "premio": premio,
                                "link": SITE_MAP.get(sala, {}).get("link", LINK_FIXO),
                                "lang": SITE_MAP.get(sala, {}).get("lang", "en"),
                                "senha_hora": senha_hora,
                                "site": site
                            }
                            freerolls.append(freeroll)
                            print(f"Freeroll adicionado: {nome} na {sala}")
                except Exception as e:
                    logging.error(f"Erro ao processar torneio em {site}: {e}")
                    continue
        except Exception as e:
            logging.error(f"Erro ao acessar {site}: {e}")
            continue
    
    return deduplicate_freerolls(freerolls)

# Função para verificar senha em horário específico
def verificar_senha_futuro(freeroll):
    if freeroll["senha_hora"] and freeroll["senha"] == "No password required":
        now = datetime.now(zoneinfo.ZoneInfo("UTC"))
        if now >= freeroll["senha_hora"]:
            print(f"Verificando senha para {freeroll['nome']} em {freeroll['site']}")
            soup = scrape_dynamic_site(freeroll["site"])
            if soup:
                torneio = soup.find("div", class_=["tournament-block", "freeroll"], text=freeroll["nome"])
                if torneio:
                    senha = torneio.find(["td", "div"], class_=["password", "pass"])
                    freeroll["senha"] = senha.text.strip() if senha else "No password required"
            if freeroll["senha"] == "No password required":
                schedule.every(4).minutes.do(verificar_senha_futuro, freeroll).tag(f"retry-{freeroll['nome']}")
                return schedule.CancelJob
    return freeroll

# Função para criar texto do post
def criar_texto_post(freeroll):
    templates = TEMPLATES_PT if freeroll["lang"] == "pt" else TEMPLATES_EN
    template = random.choice(templates)
    senha_text = f"Password: {freeroll['senha']}" if freeroll["senha"] != "No password required" else "No password required"
    return template.format(
        sala=freeroll["sala"].capitalize(),
        senhas=senha_text,
        link=freeroll["link"]
    )

# Função para postar freeroll
def post_freeroll(freeroll):
    texto = criar_texto_post(freeroll)
    try:
        client.create_tweet(text=texto)
        print(f"Postado: {texto}")
        with open("posts_log.txt", "a") as f:
            f.write(f"{datetime.now(zoneinfo.ZoneInfo('UTC'))}: {texto}\n")
    except Exception as e:
        logging.error(f"Erro ao postar: {e}")

# Função para agendar posts e verificações de senha
def schedule_posts(freerolls):
    posted = 0
    for freeroll in freerolls[:12]:  # Limite de 12 posts por dia
        if freeroll["senha_hora"]:
            schedule.every().day.at(freeroll["senha_hora"].strftime("%H:%M")).do(verificar_senha_futuro, freeroll)
        post_time = freeroll["data_hora"] - timedelta(hours=1)
        schedule.every().day.at(post_time.strftime("%H:%M")).do(post_freeroll, freeroll)
        posted += 1

# Função principal
def main():
    freerolls = obter_freerolls()
    if not freerolls:
        print("Nenhum freeroll encontrado.")
        return
    schedule_posts(freerolls)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
