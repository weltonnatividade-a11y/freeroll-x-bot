import requests
from bs4 import BeautifulSoup
import tweepy
import os

# Chaves do X API (use secrets no GitHub para não expor)
API_KEY = os.getenv('X_API_KEY')
API_SECRET = os.getenv('X_API_SECRET')
ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN')
ACCESS_SECRET = os.getenv('X_ACCESS_SECRET')

# Setup Tweepy para API v2 (free tier)
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# Função para scrape freerolls (exemplo: FreerollPass)
def get_daily_freerolls():
    url = 'https://freerollpass.com/'  # Site com schedule diário
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Exemplo de parsing (ajuste seletores com inspetor F12)
    freerolls = []
    for item in soup.find_all('div', class_='freeroll-item'):  # Seletor genérico — adapte!
        time = item.find('span', class_='time').text if item.find('span', class_='time') else 'TBD'
        site = item.find('span', class_='site').text if item.find('span', class_='site') else 'Vários'
        prize = item.find('span', class_='prize').text if item.find('span', class_='prize') else '$?'
        freerolls.append(f"{time} - {site}: {prize}")
    
    return freerolls[:3]  # Pega top 3 para o tweet

# Posta o tweet
def post_tweet():
    freerolls = get_daily_freerolls()
    if not freerolls:
        tweet = "Sem freerolls hoje? Fique ligado para updates! #PokerFreeroll"
    else:
        list_str = '\n'.join(freerolls)
        tweet = f"Freerolls do dia! 🔥\n{list_str}\nJunte-se e ganhe grátis! #Poker #Freeroll\nMais em freerollpass.com"
    
    try:
        api.update_status(tweet)
        print("Tweet postado com sucesso!")
    except Exception as e:
        print(f"Erro no post: {e}")

if __name__ == "__main__":
    post_tweet()
