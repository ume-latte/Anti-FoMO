import os
import requests
from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Spotify 相關設定
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

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

            if "連接spotify" in text:
                auth_url = generate_spotify_auth_url()
                reply_text = f"請點擊以下連結以連接你的Spotify帳戶: {auth_url}，連結後你可以輸入「推薦歌曲」，來獲得好歌推薦！"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

            elif "推薦歌曲" in text:
                reply_text = search_song("FoMO")
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
            elif "推薦播放清單" in text:
                reply_text = recommend_playlist()
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    
    return 'OK'

# 生成 Spotify 授權 URL
def generate_spotify_auth_url():
    auth_params = {
        'client_id': SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'scope': 'user-read-private user-read-email'
    }
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={auth_params['client_id']}&response_type={auth_params['response_type']}&redirect_uri={auth_params['redirect_uri']}&scope={auth_params['scope']}"
    return auth_url

# 推薦歌曲
def search_song(query):
    access_token = get_spotify_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    search_url = f"https://api.spotify.com/v1/search?q={query}&type=track&limit=1"
    response = requests.get(search_url, headers=headers)
    
    if response.status_code == 200:
        tracks = response.json()["tracks"]["items"]
        if tracks:
            track = tracks[0]
            song_name = track["name"]
            artist_name = track["artists"][0]["name"]
            return f"推薦歌曲：{song_name} - {artist_name}"
        else:
            return "找不到相關的歌曲。"
    else:
        return "無法搜索歌曲。"

# 推薦播放清單
def recommend_playlist():
    access_token = get_spotify_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    playlist_id = "7oJx24EcRU7fIVoTdqKscK"
    playlist_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    response = requests.get(playlist_url, headers=headers)
    
    if response.status_code == 200:
        playlist = response.json()
        playlist_name = playlist["name"]
        return f"推薦播放清單：{playlist_name}"
    else:
        return "無法推薦播放清單。"

# 獲取 Spotify 授權 token 的函式（需要根據你的實際情況來實現）
def get_spotify_access_token():
    # 此處需要根據實際情況實現獲取 Spotify 授權 token 的邏輯
    # 可以使用 OAuth2.0 進行授權，獲取 access token
    # 這裡假設你已經有了一個能夠獲取 access token 的方法
    # 如果你還沒有實現這部分，需要先完成這個部分的程式碼
    return "your_access_token_here"

# 主程式入口
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

