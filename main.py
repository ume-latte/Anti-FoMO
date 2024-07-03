import os
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests

# 初始化FastAPI和LINE Bot相關設置
app = FastAPI()
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Spotify API設置
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Spotify OAuth 2.0授權資訊
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"

# 獲取Spotify API訪問權杖的幫助函數
def get_spotify_access_token():
    payload = {
        'grant_type': 'client_credentials',
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(SPOTIFY_AUTH_URL, data=payload)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise HTTPException(status_code=500, detail="Failed to obtain Spotify access token")

# 處理LINE Bot的Webhook
@app.post("/webhooks/line")
async def handle_callback(request: Request):
    signature = request.headers['X-Line-Signature']
    body = await request.body()
    body = body.decode()
    
    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessage):
            text = event.message.text.lower()
            
            if "推薦歌曲" in text:
                access_token = get_spotify_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                search_url = f"{SPOTIFY_API_BASE_URL}/search?q=love&type=track"
                response = requests.get(search_url, headers=headers)
                
                if response.status_code == 200:
                    song_name = response.json()["tracks"]["items"][0]["name"]
                    artist_name = response.json()["tracks"]["items"][0]["artists"][0]["name"]
                    reply_text = f"這裡是一首不錯的歌曲推薦給你：{song_name} - {artist_name}"
                else:
                    reply_text = "抱歉，無法獲取歌曲推薦。"
                
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
            elif "推薦播放清單" in text:
                access_token = get_spotify_access_token()
                headers = {"Authorization": f"Bearer {access_token}"}
                playlist_url = f"{SPOTIFY_API_BASE_URL}/playlists/{playlist_id}"
                response = requests.get(playlist_url, headers=headers)
                
                if response.status_code == 200:
                    playlist_name = response.json()["name"]
                    reply_text = f"這裡是一個不錯的播放清單推薦給你：{playlist_name}"
                else:
                    reply_text = "抱歉，無法獲取播放清單推薦。"
                
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
