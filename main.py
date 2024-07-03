from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os
import random

app = FastAPI()
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

#獲取Spotify API訪問令牌
SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/api/token'
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

def get_spotify_access_token():
    payload = {
        'grant_type': 'client_credentials',
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(SPOTIFY_AUTH_URL, data=payload)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception("Failed to obtain Spotify access token")

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

#推薦歌曲和播放清單函數
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



#使用Spotify的推薦API
#更新search_song和recommend_playlist函數來根據使用者的聽歌歷史推薦歌曲。
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
            playlist = [f"{track['name']} - {track['artists'][0]['name']}" for track in tracks]
            return "推薦播放清單：\n" + "\n".join(playlist)
        else:
            return "找不到相關的播放清單。"
    else:
        return "無法推薦播放清單。"


#整合到LINE Bot
@app.post("/webhooks/line")
async def handle_callback(request: Request):
    signature = request.headers['X-Line-Signature']
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
