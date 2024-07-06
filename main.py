from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
from firebase import firebase
from fastapi.responses import HTMLResponse, RedirectResponse

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Spotify API 設定
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')  # 從環境變量中讀取

# Firebase 設定
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# 生成 Spotify 授權 URL
def generate_spotify_auth_url():
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=user-read-private user-read-email"
    return auth_url

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

# 獲取使用者的 Spotify 訪問令牌
def get_user_spotify_token(user_id):
    token = get_spotify_token(user_id)
    if not token:
        raise HTTPException(status_code=400, detail="找不到 Spotify 令牌")
    return token

# 推薦歌曲函數
def recommend_song(user_id):
    token = get_user_spotify_token(user_id)
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    # 使用 Spotify API 獲取推薦的歌曲
    endpoint = 'https://api.spotify.com/v1/recommendations'
    params = {
        'limit': 1,  # 限制推薦結果為一首歌曲
        'seed_genres': 'pop',  # 指定推薦流派為 pop，你可以根據需要調整
    }
    response = requests.get(endpoint, headers=headers, params=params)

    if response.status_code == 200:
        song_data = response.json()['tracks'][0]
        song_name = song_data['name']
        artist_name = song_data['artists'][0]['name']
        return f"推薦給你的歌曲是：{song_name} - {artist_name}"
    else:
        return "無法獲取推薦歌曲，請稍後重試。"

# 推薦播放清單函數
def recommend_playlist(user_id):
    token = get_user_spotify_token(user_id)
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    # 使用 Spotify API 獲取推薦的播放清單
    endpoint = 'https://api.spotify.com/v1/me/playlists'
    params = {
        'limit': 1,  # 限制推薦結果為一個播放清單
    }
    response = requests.get(endpoint, headers=headers, params=params)

    if response.status_code == 200:
        playlist_data = response.json()['items'][0]
        playlist_name = playlist_data['name']
        playlist_url = playlist_data['external_urls']['spotify']
        return f"這是一個推薦的播放清單：{playlist_name}\n{playlist_url}"
    else:
        return "無法獲取推薦播放清單，請稍後重試。"

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

            if "連接spotify" in text:
                auth_url = generate_spotify_auth_url()
                reply_text = f"請點擊以下連結以連接你的Spotify帳戶: {auth_url}"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

            elif "推薦歌曲" in text:
                reply_text = recommend_song(user_id)
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

            elif "推薦播放清單" in text:
                reply_text = recommend_playlist(user_id)
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    return 'OK'

# 處理 Spotify 的回調請求
@app.get("/callback")
async def spotify_callback(request: Request, code: str):
    if code:
        token = exchange_code_for_token(code)
        # 在這裡保存訪問令牌，關聯到用戶
        return "Spotify 授權成功！你現在可以回到 LINE 並使用 Spotify 功能。"
    else:
        return "授權失敗，請重試。"

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
