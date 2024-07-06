from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
import random

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

#儲存使用者的聽歌歷史
from firebase import firebase

firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

def save_user_history(user_id, track):
    user_history_path = f'history/{user_id}'
    history = fdb.get(user_history_path, None)
    if history is None:
        history = []
    history.append(track)
    fdb.put(user_history_path, None, history)
    
# 推薦歌曲函數
import random

def get_user_history(user_id):
    user_history_path = f'history/{user_id}'
    history = fdb.get(user_history_path, None)
    if history is None:
        history = []
    return history

def recommend_song(user_id):
    access_token = get_spotify_access_token()
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
    access_token = get_spotify_access_token()
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
                reply_text = search_song()
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
