import logging
import os
import re
import sys
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import uvicorn
import requests
from firebase import firebase
import google.generativeai as genai
from utils import check_image_quake, check_location_in_message, get_current_weather, get_weather_data, simplify_data

logging.basicConfig(level=os.getenv('LOG', 'WARNING'))
logger = logging.getLogger(__name__)

# Initialize FastAPI and LineBot
app = FastAPI()

line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Firebase Configuration
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# Gemini API Configuration
gemini_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=gemini_key)

# Spotify Configuration
spotify_tracks = [
    "https://open.spotify.com/track/3E5XrOtqMAs7p2wKhwgOjf",
    "https://open.spotify.com/track/3RauEVgRgj1IuWdJ9fDs70",
    "https://open.spotify.com/track/1dNIEtp7AY3oDAKCGg2XkH",
    "https://open.spotify.com/track/76N7FdzCI9OsiUnzJVLY2m",
    "https://open.spotify.com/track/09CtPGIpYB4BrO8qb1RGsF",
    "https://open.spotify.com/track/7iuHBHtxQNKRTGKkYpXmGM",
    "https://open.spotify.com/track/2JdzcxKSk7raYujsLYUXvi",
    "https://open.spotify.com/track/1yTQ39my3MoNROlFw3RDNy",
    "https://open.spotify.com/track/1z3ugFmUKoCzGsI6jdY4Ci",
    "https://open.spotify.com/track/4o6BgsqLIBViaGVbx5rbRk"
]

# Initialize Spotify URLs in Firebase
for index, track_url in enumerate(spotify_tracks, start=1):
    fdb.put('/spotify_tracks', f'track_{index}', track_url)

# FastAPI Health Check
@app.get("/health")
async def health():
    return 'ok'

# LineBot Webhook Handler
@app.post("/webhooks/line")
async def handle_callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body = body.decode()
    
    logging.info(f"Request body: {body}")
    logging.info(f"Signature: {signature}")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        logging.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            text = event.message.text.lower()
            user_id = event.source.user_id
            
            try:
                if "su3g4u dk vu ej8 " in text:
                    auth_url = generate_spotify_auth_url()
                    reply_text = f"請點擊以下連結以連接你的Spotify帳戶: {auth_url}"
                    await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
                elif "推薦歌曲" in text:
                    reply_text = recommend_song(user_id)
                    await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

                elif "推薦播放清單" in text:
                    reply_text = recommend_playlist(user_id)
                    await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
                # Add more conditions as needed
            except Exception as e:
                logging.error(f"Error processing event: {e}")
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text="處理請求時發生錯誤，請稍後再試。"))

    return 'OK'

# Spotify Authorization Callback
@app.get("/callback")
async def spotify_callback(request: Request, code: str):
    try:
        if code:
            token = exchange_code_for_token(code)
            if token:
                # Save access token and associate it with user
                return "Spotify authorization successful! You can now go back to LINE and use Spotify features."
            else:
                return "Authorization failed, please try again."
        else:
            return "Authorization failed, please try again."
    except Exception as e:
        logging.error(f"Error during Spotify callback: {e}")
        return "Authorization failed, please try again."

# Helper functions
def generate_spotify_auth_url():
    SPOTIFY_AUTH_URL = os.getenv('SPOTIFY_AUTH_URL')
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=user-read-private user-read-email"
    return auth_url

def exchange_code_for_token(code):
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
    
    token_url = "https://accounts.spotify.com/api/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        logging.error(f"Failed to exchange code for token: {response.text}")
        return None

def recommend_song(user_id):
    user_history = get_user_history(user_id)
    spotify_tracks = fdb.get('/spotify_tracks', None)
    
    if spotify_tracks:
        random_track_url = random.choice(list(spotify_tracks.values()))
        return f"推薦歌曲：您可以在這裡收聽歌曲：{random_track_url}"
    else:
        return "找不到相關的歌曲。"

def recommend_playlist(user_id):
    spotify_playlist_url = fdb.get('/spotify_playlist_url', None)
    if spotify_playlist_url:
        return f"推薦播放清單：您可以在這裡收聽播放清單：{spotify_playlist_url}"
    else:
        return "找不到相關的播放清單。"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', default=8080))
    debug = True if os.environ.get('API_ENV', default='develop') == 'develop' else False
    logging.info('Application will start...')
    uvicorn.run(app, host="0.0.0.0", port=port, debug=debug)
