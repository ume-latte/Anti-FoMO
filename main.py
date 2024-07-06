from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
from bs4 import BeautifulSoup

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# 爬取推薦歌曲
def recommend_song():
    url = "https://www.spotify.com/us/playlist/37i9dQZF1DXcBWIGoYBM5M"  # 替換為實際的 Spotify 播放清單 URL
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        songs = soup.find_all('span', troye sivan_='track-name')  # 假設這是歌曲名稱的 class
        artists = soup.find_all('span', troye sivan_='artists')  # 假設這是藝術家名稱的 class
        if songs and artists:
            song_name = songs[0].get_text()
            artist_name = artists[0].get_text()
            return f"推薦給你的歌曲是：{song_name} - {artist_name}"
        else:
            return "找不到推薦歌曲。"
    else:
        return "無法獲取推薦歌曲，請稍後重試。"

# 爬取推薦播放清單
def recommend_playlist():
    url = "https://open.spotify.com/playlist/7oJx24EcRU7fIVoTdqKscK"  # 替換為實際的 Spotify 播放清單 URL
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        songs = soup.find_all('span', class_='track-name')  # 假設這是歌曲名稱的 class
        artists = soup.find_all('span', class_='artists')  # 假設這是藝術家名稱的 class
        if songs and artists:
            playlist = []
            for song, artist in zip(songs, artists):
                song_name = song.get_text()
                artist_name = artist.get_text()
                playlist.append(f"{song_name} - {artist_name}")
            return "推薦播放清單：\n" + "\n\n".join(playlist)
        else:
            return "找不到推薦播放清單。"
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

            if "推薦歌曲" in text:
                reply_text = recommend_song()
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

            elif "推薦播放清單" in text:
                reply_text = recommend_playlist()
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

    return 'OK'

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
