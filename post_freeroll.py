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

# Salas e afiliados (links completos)
SITE_MAP = {
    'coinpoker': {'lang': 'pt', 'link': 'https://record.coinpokeraffiliates.com/_zcOgBAtPAXHUOsjNOfgKeWNd7ZgqdRLk/1/'},
    '888poker': {'lang': 'pt', 'link': 'https://ic.aff-handler.com/c/48566?sr=1068421'},
    'unibetpoker': {'lang': 'en', 'link': 'https://publisher.pokeraffiliatesolutions.com/outgoing_campaign/78382?type=1'},
    'redstar': {'lang': 'en', 'link': ''},
    'wpt': {'lang': 'pt', 'link': 'https://tracking.wptpartners.com/visit/?bta=838&nci=5373&utm_campaign=wptpok1030'},
    'betsson': {'lang': 'pt', 'link': ''},
    'pokerstars': {'lang': 'en', 'link': ''},
    'americas cardroom': {'lang': 'en', 'link': 'https://record.secure.acraffiliates.com/_X7ahir
