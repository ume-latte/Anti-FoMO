from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
from firebase_admin import credentials, db, initialize_app

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Spotify API 設定
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

# Firebase 設定
cred = credentials.Certificate('/path/to/serviceAccountKey.json')  # 替換為你的服務帳戶金鑰路徑
initialize_app(cred)
ref = db.reference('spotify_playlists')

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
    ref.child(f'spotify_tokens/{user_id}').set({'token': token})

def get_spotify_token(user_id):
    snapshot = ref.child(f'spotify_tokens/{user_id}').get()
    return snapshot.get('token') if snapshot else None

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
                reply_text = f"請點擊以下連結以連接你的 Spotify 帳戶: {auth_url}"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

            elif "推薦歌曲" in text:
                reply_text = recommend_playlist_to_firebase(user_id)
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    return 'OK'

# 推薦歌曲函數，將歌單歌曲存入 Firebase
def recommend_playlist_to_firebase(user_id):
    try:
        playlist_id = '7oJx24EcRU7fIVoTdqKscK'  # Spotify 歌單 ID
        access_token = get_spotify_token(user_id)
        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        playlist_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        response = requests.get(playlist_url, headers=headers)

        if response.status_code == 200:
            tracks = response.json().get("items", [])
            if tracks:
                playlist_data = {
                    'name': 'Recommended Playlist',  # 歌單名稱
                    'tracks': []
                }
                for track in tracks:
                    track_info = {
                        'id': track['track']['id'],
                        'name': track['track']['name'],
                        'artist': track['track']['artists'][0]['name'],
                        'uri': track['track']['external_urls']['spotify']
                    }
                    playlist_data['tracks'].append(track_info)

                ref.child(playlist_id).set(playlist_data)
                return "已成功將推薦歌單存入 Firebase."
            else:
                return "找不到歌曲清單。"
        else:
            print(f"Spotify API 請求失敗，狀態碼：{response.status_code}，回應：{response.text}")
            return "無法獲取歌曲清單。"
    except Exception as e:
        print(f"發生錯誤：{str(e)}")
        return "處理過程中出現錯誤。"

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
