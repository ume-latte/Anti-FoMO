from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import random
import logging
import requests
from firebase import firebase

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化日誌
logging.basicConfig(level=logging.INFO)

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Firebase 設定
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# 生成 Spotify 授權 URL
def generate_spotify_auth_url():
    SPOTIFY_AUTH_URL = os.getenv('SPOTIFY_AUTH_URL')
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=user-read-private user-read-email"
    return auth_url

# 定義 exchange_code_for_token 函數
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

# 將歌曲 URL 寫入 Firebase
for index, track_url in enumerate(spotify_tracks, start=1):
    fdb.put('/spotify_tracks', f'track_{index}', track_url)

# 儲存和使用訪問令牌
def save_user_history(user_id, track_info):
    user_history_path = f'history/{user_id}'
    history = fdb.get(user_history_path, None)
    if history is None:
        history = []
    history.append(track_info)
    fdb.put('', user_history_path, history)

def get_user_history(user_id):
    user_history_path = f'history/{user_id}'
    history = fdb.get(user_history_path, None)
    if history is None:
        history = []
    return history

# 推薦歌曲和播放清單函數
def recommend_song(user_id):
    user_history = get_user_history(user_id)
    
    # 從 firebase 中取得 spotify_tracks
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

# 處理 LINE Webhook 請求
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
            except Exception as e:
                logging.error(f"Error processing event: {e}")
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text="處理請求時發生錯誤，請稍後再試。"))

# 處理 Spotify 的回調請求
@app.get("/callback")
async def spotify_callback(request: Request, code: str):
    try:
        if code:
            token = exchange_code_for_token(code)
            if token:
                # 在這裡保存訪問令牌，關聯到用戶
                return "Spotify authorization successful! You can now go back to LINE and use Spotify features."
            else:
                return "Authorization failed, please try again."
        else:
            return "Authorization failed, please try again."
    except Exception as e:
        logging.error(f"Error during Spotify callback: {e}")
        return "Authorization failed, please try again."

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
