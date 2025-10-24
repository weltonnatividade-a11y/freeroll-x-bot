import os
import tweepy
import requests
from bs4 import BeautifulSoup
import random
import time
import re
from datetime import datetime, timedelta
import zoneinfo
import logging
from difflib import SequenceMatcher
import schedule

# Configuração de logging
logging.basicConfig(filename='bot_errors.log', level=logging.ERROR)

# Chaves do X (comente se testando sem postar)
api_key = os.getenv('TWITTER_API_KEY')
api_secret = os.getenv('TWITTER_API_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')

if all([api_key, api_secret, access_token, access_token_secret]):
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    print("Conexão com Twitter/X inicializada com sucesso")
else:
    client = None
    print("Sem chaves Twitter - modo dry run (só printa, não posta)")

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

# Mapeamento de salas e links de afiliados (adiciona mais baseados nos sites atuais)
SITE_MAP = {
    'wpt': {'lang': 'en', 'link': 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'},
    'coinpoker': {'lang': 'pt', 'link': 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'},
    '888poker': {'lang': 'pt', 'link': 'https://ic.aff-handler.com/c/48566?sr=1068421'},
    'unibet': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'},
    'redstar': {'lang': 'en', 'link': 'LINK_FIXO'},  # Adicione se tiver
    'pokestars': {'lang': 'en', 'link': 'LINK_FIXO'},
    'stake': {'lang': 'en', 'link': 'https://stake.bet/?c=TsaKFUEF'},
    # ... (mantenha os originais se quiser)
}

LINK_FIXO = "https://linkr.bio/pokersenha"

# Função para parsear data e horário (melhorada pra tempos relativos)
def parse_horario_torneio(data_str, hora_str=None, timezone_str="UTC"):
    try:
        data_str = (data_str or hora_str or "").strip().lower()
        now = datetime.now(zoneinfo.ZoneInfo("UTC"))
        # Tempos relativos como "20 minutes to start"
        if "minute" in data_str or "hour" in data_str:
            minutes = re.search(r'(\d+) (minutes?|hours?)', data_str)
            if minutes:
                mins = int(minutes.group(1)) * (60 if "hour" in minutes.group(2) else 1)
                return now + timedelta(minutes=mins)
        # Datas absolutas
        if hora_str:
            data_hora_str = f"{data_str} {hora_str}"
        else:
            data_hora_str = data_str
        formatos = [
            "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%B %d, %Y %I:%M %p", "%d %B %Y %H:%M"
        ]
        for fmt in formatos:
            try:
                dt = datetime.strptime(data_hora_str, fmt)
                timezone = zoneinfo.ZoneInfo(timezone_str)
                dt = dt.replace(tzinfo=timezone).astimezone(zoneinfo.ZoneInfo("UTC"))
                return dt
            except ValueError:
                continue
        return now  # Fallback pra agora se não parsear
    except Exception as e:
        logging.error(f"Erro ao parsear data/hora: {e}")
        return None

def limpar_url(url):
    return re.sub(r'#.*', '', url.strip())  # Remove anchors como #freerolls-today

def deduplicate_freerolls(freerolls):
    unique_freerolls = []
    for freeroll in freerolls:
        is_duplicate = any(
            freeroll["sala"] == u["sala"] and
            abs((freeroll.get("data_hora", datetime.now()) - u.get("data_hora", datetime.now())).total_seconds()) < 3600 and  # 1h tolerance
            SequenceMatcher(None, freeroll["nome"], u["nome"]).ratio() > 0.7
            for u in unique_freerolls
        )
        if not is_duplicate:
            unique_freerolls.append(freeroll)
    return unique_freerolls

# Função para obter freerolls (parsing flexível por site)
def obter_freerolls():
    freerolls = []
    now = datetime.now(zoneinfo.ZoneInfo("UTC"))
    tomorrow = now + timedelta(days=1)
    
    for site in SITES:
        site_clean = limpar_url(site)
        print(f"Tentando acessar: {site_clean}")
        try:
            response = requests.get(site_clean, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Parsing por site, mais genérico
            if "pokerlistings.com" in site:
                # Tabela com <tr> genéricas
                torneios = soup.find_all("tr") or soup.find_all("div", class_=re.compile(r"tournament|freeroll|event"))
            elif "freerollpasswords.com" in site:
                # Blog-style: busca seções com headings e <p> labels
                torneios = soup.find_all(["h3", "div"], string=re.compile(r"\$|Freeroll|WPT"))
            elif "pokerfreerollpasswords.com" in site:
                # Blocos com labels como "DATE", "NAME"
                torneios = soup.find_all("div", string=re.compile(r"DATE|TIME|Password")) or soup.find_all("p")
            elif "freerollpass.com" in site:
                # Tabela summary + dinâmica
                torneios = soup.find_all("table") or soup.find_all("tr", class_=re.compile(r"row|item"))
            else:
                torneios = soup.find_all(["tr", "div"], class_=re.compile(r"freeroll|tournament|row"))
            
            print(f"Torneios potenciais em {site}: {len(torneios)}")
            
            for torneio in torneios[:20]:  # Limite pra não flood
                try:
                    # Parsing genérico por texto (busca labels)
                    text = torneio.get_text().strip()
                    if not text or len(text) < 50: continue
                    
                    # Nome: busca perto de "Name:" ou título
                    nome_match = re.search(r"Name:\s*(.+?)(?:\n|$|Date|Time)", text, re.I)
                    nome = nome_match.group(1).strip() if nome_match else re.search(r"Freeroll\s*(.+?)(?:\s*\$|Date)", text).group(1).strip() if re.search(r"Freeroll", text) else "Freeroll Sem Nome"
                    
                    # Sala: busca rooms conhecidas ou links
                    sala_lower = re.search(r"(wpt|coinpoker|888poker|unibet|redstar|stake|pokestars)(?:\s|$)", text, re.I)
                    sala = sala_lower.group(1).lower() if sala_lower else next((k for k in SITE_MAP if k in text.lower()), None)
                    if not sala: continue
                    
                    # Data/Hora: busca "Date:", "Time:", ou relativos
                    data_match = re.search(r"Date:\s*(.+?)(?:\n|$)", text, re.I)
                    data = data_match.group(1).strip() if data_match else None
                    hora_match = re.search(r"Time:\s*(.+?)(?:\n|$|Password)", text, re.I)
                    hora = hora_match.group(1).strip() if hora_match else re.search(r"(\d{1,2}:\d{2}\s*(CET|GMT|to start))", text)
                    hora = hora.group(1) if hora else None
                    
                    # Senha: busca "Password:"
                    senha_match = re.search(r"Password:\s*(.+?)(?:\n|$)", text, re.I)
                    senha = senha_match.group(1).strip() if senha_match else "No password required"
                    
                    # Prêmio: busca $ ou €
                    premio_match = re.search(r"Prize Pool:\s*(.+?)(?:\n|$)|\$?€?(\d+(?:,\d+)?)", text, re.I)
                    premio = premio_match.group(1) or premio_match.group(2) or "Not informed"
                    
                    data_hora = parse_horario_torneio(data, hora)
                    if data_hora and now <= data_hora <= tomorrow:
                        freeroll = {
                            "nome": nome[:50],  # Limite pra tweet
                            "sala": sala,
                            "data_hora": data_hora,
                            "senha": senha,
                            "premio": premio,
                            "link": SITE_MAP.get(sala, {}).get("link", LINK_FIXO),
                            "lang": SITE_MAP.get(sala, {}).get("lang", "en"),
                            "site": site
                        }
                        freerolls.append(freeroll)
                        print(f"Freeroll adicionado: {nome} na {sala} - {data_hora} - Senha: {senha}")
                except Exception as e:
                    logging.error(f"Erro processando em {site}: {e}")
                    continue
        except Exception as e:
            print(f"Erro acessando {site}: {e}")
            logging.error(f"Erro acessando {site}: {e}")
            continue
    
    unique = deduplicate_freerolls(freerolls)
    print(f"\n=== RESUMO: {len(unique)} freerolls únicos ===")
    for f in unique:
        print(f"- {f['nome']} | {f['sala']} | {f['data_hora'].strftime('%H:%M')} | {f['senha']} | {f['premio']}")
    return unique

# Templates (mantidos)
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

def criar_texto_post(freeroll):
    templates = TEMPLATES_PT if freeroll["lang"] == "pt" else TEMPLATES_EN
    template = random.choice(templates)
    senha_text = f"Senha: {freeroll['senha']}" if freeroll["senha"] != "No password required" else "Sem senha"
    return template.format(sala=freeroll["sala"].title(), senhas=senha_text, link=freeroll["link"])

def post_freeroll(freeroll):
    texto = criar_texto_post(freeroll)
    print(f"[DRY RUN] Texto pronto: {texto}")  # Simula
    if client:  # Descomente pra postar real
        # try:
        #     client.create_tweet(text=texto)
        #     print(f"POSTADO no X: {texto}")
        # except Exception as e:
        #     logging.error(f"Erro postando: {e}")
        pass

# Main simples: scrape e post imediato (sem schedule pra teste)
def main():
    freerolls = obter_freerolls()
    if not freerolls:
        print("Nenhum freeroll válido nas próximas 24h. Tenta amanhã!")
        return
    for f in freerolls[:5]:  # Top 5 pra teste
        post_freeroll(f)
        time.sleep(60)  # Delay anti-spam

if __name__ == "__main__":
    main()
