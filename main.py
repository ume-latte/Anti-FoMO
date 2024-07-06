from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import random
from firebase import firebase

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Firebase 設定
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)
spotify_playlist_url = "https://open.spotify.com/playlist/7oJx24EcRU7fIVoTdqKscK"
fdb.put('', '/spotify_playlist_url', spotify_playlist_url)

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

    if user_history:
        recommended_track = random.choice(user_history)
        song_name = recommended_track["name"]
        artist_name = recommended_track["artist"]
        track_url = recommended_track["url"]
        return f"推薦歌曲：{song_name} - {artist_name}\n[點此收聽]({track_url})"
    else:
        return "找不到相關的歌曲。"

def recommend_playlist(user_id):
    user_history = get_user_history(user_id)

    if user_history:
        random.shuffle(user_history)
        playlist = []
        for track in user_history[:10]:  # 推薦前 10 首歌曲
            song_name = track["name"]
            artist_name = track["artist"]
            track_url = track["url"]
            playlist.append(f"{song_name} - {artist_name}\n[點此收聽]({track_url})")
        return "推薦播放清單：\n" + "\n\n".join(playlist)
    else:
        return "找不到相關的播放清單。"

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
                reply_text = recommend_song(user_id)
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
