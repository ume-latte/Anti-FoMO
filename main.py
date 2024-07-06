from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
import random
from firebase import firebase
from fastapi.responses import HTMLResponse, RedirectResponse
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Spotify API 設定
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# Firebase 設定
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# 生成 Spotify 認證管理器
auth_manager = SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=auth_manager)

# 交換授權碼為訪問令牌
def exchange_code_for_token(code):
    token_url = 'https://accounts.spotify.com/api/token'
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(token_url, data=payload)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise HTTPException(status_code=400, detail="Failed to obtain Spotify access token")

# 儲存和使用訪問令牌
def save_spotify_token(user_id, token):
    fdb.put(f'spotify_tokens/{user_id}', 'token', token)

def get_spotify_token(user_id):
    return fdb.get(f'spotify_tokens/{user_id}', 'token')

# 推薦歌曲和播放清單函數
def recommend_song():
    recommendations = sp.recommendations(seed_genres=['pop', 'rock', 'classical'], limit=50)
    track = random.choice(recommendations['tracks'])
    return f"隨機推薦歌曲: {track['name']} by {', '.join([artist['name'] for artist in track['artists']])}"

def recommend_playlist():
    playlists = sp.search(q='year:2023', type='playlist', limit=50)
    playlist = random.choice(playlists['playlists']['items'])
    return f"隨機推薦播放清單: {playlist['name']} - {playlist['external_urls']['spotify']}"

# 處理 LINE Webhook 請求
@app.post("/webhooks/line")
async def handle_callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
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

            if "推薦歌曲" in text:
                reply_text = recommend_song()
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

            elif "推薦播放清單" in text:
                reply_text = recommend_playlist()
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    return 'OK'

# 處理 Spotify 的回調請求
@app.get("/callback")
async def spotify_callback(request: Request, code: str):
    if code:
        token = exchange_code_for_token(code)
        # 在這裡保存訪問令牌，關聯到用戶
        return "Spotify authorization successful! You can now return to LINE and use Spotify features."
    else:
        return "Authorization failed, please try again."

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
