from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
from firebase import firebase
from bs4 import BeautifulSoup

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Firebase 設定
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# 推薦歌曲函數
def recommend_song():
    url = "https://open.spotify.com/playlist/7oJx24EcRU7fIVoTdqKscK"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        songs = soup.find_all('span', class_='track-name')
        artists = soup.find_all('span', class_='artists-albums')
        if songs and artists:
            song_name = songs[0].get_text()
            artist_name = artists[0].get_text()
            return f"推薦給你的歌曲是：{song_name} - {artist_name}"
        else:
            return "找不到推薦歌曲。"
    else:
        return "無法獲取推薦歌曲，請稍後重試。"

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
                reply_text = recommend_playlist(user_id)
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    return 'OK'

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
