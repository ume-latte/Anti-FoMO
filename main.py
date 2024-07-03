import logging
import os
import re
import sys
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Request
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage
)
import uvicorn
from dotenv import load_dotenv

if os.getenv('API_ENV') != 'production':
    load_dotenv()

app = FastAPI()

logging.basicConfig(level=os.getenv('LOG', 'WARNING'))
logger = logging.getLogger(__file__)

channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
if not channel_secret or not channel_access_token:
    logger.error('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')

@app.get("/health")
async def health():
    return 'ok'

@app.get("/spotify/login")
async def spotify_login():
    scope = "user-read-playback-state user-modify-playback-state"
    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?response_type=code&client_id={spotify_client_id}"
        f"&scope={scope}&redirect_uri={spotify_redirect_uri}"
    )
    return {"url": auth_url}

@app.get("/spotify/callback")
async def spotify_callback(code: str):
    token_url = "https://accounts.spotify.com/api/token"
    response = requests.post(token_url, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": spotify_redirect_uri,
        "client_id": spotify_client_id,
        "client_secret": spotify_client_secret
    })
    response_data = response.json()
    access_token = response_data.get("access_token")
    refresh_token = response_data.get("refresh_token")
    return {"access_token": access_token, "refresh_token": refresh_token}

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
            user_id = event.source.user_id
            
            if text == "正在播放":
                # 獲取正在播放的歌曲資訊
                access_token = ""  # 這裡需要處理如何保存和獲取用戶的access token
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get("https://api.spotify.com/v1/me/player/currently-playing", headers=headers)
                
                if response.status_code == 200 and response.json():
                    song_info = response.json()
                    song_name = song_info["item"]["name"]
                    artists = ", ".join([artist["name"] for artist in song_info["item"]["artists"]])
                    reply_text = f"你正在聽 {song_name} 由 {artists} 演唱。"
                else:
                    reply_text = "目前沒有正在播放的歌曲。"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            elif text == "播放":
                # 播放音樂
                access_token = ""  # 這裡需要處理如何保存和獲取用戶的access token
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.put("https://api.spotify.com/v1/me/player/play", headers=headers)
                if response.status_code == 204:
                    reply_text = "音樂已播放。"
                else:
                    reply_text = "無法播放音樂。"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            elif text == "暫停":
                # 暫停音樂
                access_token = ""  # 這裡需要處理如何保存和獲取用戶的access token
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.put("https://api.spotify.com/v1/me/player/pause", headers=headers)
                if response.status_code == 204:
                    reply_text = "音樂已暫停。"
                else:
                    reply_text = "無法暫停音樂。"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            elif text == "跳過":
                # 跳過歌曲
                access_token = ""  # 這裡需要處理如何保存和獲取用戶的access token
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.post("https://api.spotify.com/v1/me/player/next", headers=headers)
                if response.status_code == 204:
                    reply_text = "已跳過當前歌曲。"
                else:
                    reply_text = "無法跳過歌曲。"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            else:
                reply_text = "未知命令，請使用 '正在播放', '播放', '暫停' 或 '跳過'。"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', default=8080))
    debug = True if os.environ.get('API_ENV', default='develop') == 'develop' else False
    logging.info('Application will start...')
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=debug)
