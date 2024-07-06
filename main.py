from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
import random
from firebase import firebase
from fastapi.responses import HTMLResponse, RedirectResponse

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Spotify API 設定
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
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
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=400, detail="無法獲取 Spotify 訪問令牌")

# 刷新訪問令牌
def refresh_spotify_token(refresh_token):
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=400, detail="無法刷新 Spotify 訪問令牌")

# 儲存和使用訪問令牌
def save_spotify_token(user_id, token_data):
    fdb.put(f'spotify_tokens/{user_id}', 'token_data', token_data)

def get_spotify_token_data(user_id):
    return fdb.get(f'spotify_tokens/{user_id}', 'token_data')

# 處理 LINE Webhook 請求
@app.post("/webhooks/line")
async def handle_callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="無效的簽名")

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
        token_data = exchange_code_for_token(code)
        save_spotify_token(request.client.host, token_data)  # 儲存訪問令牌，關聯到用戶
        return "Spotify 授權成功！你現在可以回到 LINE 並使用 Spotify 功能。"
    else:
        return "授權失敗，請重試。"

# 推薦歌曲和播放清單函數
def get_user_history(user_id):
    user_history_path = f'history/{user_id}'
    history = fdb.get(user_history_path, None)
    if history is None:
        history = []
    return history

def save_user_history(user_id, track_info):
    user_history_path = f'history/{user_id}'
    history = get_user_history(user_id)
    history.append(track_info)
    fdb.put(user_history_path, 'tracks', history)

def get_valid_spotify_token(user_id):
    token_data = get_spotify_token_data(user_id)
    if token_data:
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        token_expiry = token_data.get('expires_in')

        # 檢查訪問令牌是否過期
        if access_token and refresh_token:
            if token_expiry <= 0:  # 這裡需要具體的過期檢查條件，取決於你的存儲結構
                token_data = refresh_spotify_token(refresh_token)
                save_spotify_token(user_id, token_data)
                access_token = token_data.get('access_token')

        return access_token
    else:
        raise HTTPException(status_code=401, detail="用戶未連接 Spotify")

def recommend_song(user_id):
    try:
        access_token = get_valid_spotify_token(user_id)
    except HTTPException as e:
        return str(e.detail)
        
    headers = {"Authorization": f"Bearer {access_token}"}
    user_history = get_user_history(user_id)

    if user_history:
        seed_tracks = ','.join([track['id'] for track in random.sample(user_history, min(5, len(user_history)))])
        recommend_url = f"https://api.spotify.com/v1/recommendations?seed_tracks={seed_tracks}&limit=1"
    else:
        recommend_url = "https://api.spotify.com/v1/recommendations?seed_genres=pop&limit=1"

    response = requests.get(recommend_url, headers=headers)

    if response.status_code == 200:
        tracks = response.json()["tracks"]
        if tracks:
            track = tracks[0]
            song_name = track["name"]
            artist_name = track["artists"][0]["name"]
            track_url = track["external_urls"]["spotify"]
            track_info = {'id': track['id'], 'name': song_name, 'artist': artist_name, 'url': track_url}
            save_user_history(user_id, track_info)
            return f"推薦歌曲：{song_name} - {artist_name}\n[點此收聽]({track_url})"
        else:
            return "找不到相關的歌曲。"
    else:
        return "無法推薦歌曲。"

def recommend_playlist(user_id):
    try:
        access_token = get_valid_spotify_token(user_id)
    except HTTPException as e:
        return str(e.detail)

    headers = {"Authorization": f"Bearer {access_token}"}
    user_history = get_user_history(user_id)

    if user_history:
        seed_tracks = ','.join([track['id'] for track in random.sample(user_history, min(5, len(user_history)))])
        recommend_url = f"https://api.spotify.com/v1/recommendations?seed_tracks={seed_tracks}&limit=10"
    else:
        recommend_url = "https://api.spotify.com/v1/recommendations?seed_genres=pop&limit=10"

    response = requests.get(recommend_url, headers=headers)

    if response.status_code == 200:
        tracks = response.json()["tracks"]
        if tracks:
            playlist = []
            for track in tracks:
                song_name = track["name"]
                artist_name = track["artists"][0]["name"]
                track_url = track["external_urls"]["spotify"]
                track_info = {'id': track['id'], 'name': song_name, 'artist': artist_name, 'url': track_url}
                save_user_history(user_id, track_info)
                playlist.append(f"{song_name} - {artist_name}\n[點此收聽]({track_url})")
            return "推薦播放清單：\n" + "\n\n".join(playlist)
        else:
            return "找不到相關的播放清單。"
    else:
        return "無法推薦播放清單。"

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
