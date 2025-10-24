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

def parse_horario_torneio(data_str, hora_str=None, timezone...
