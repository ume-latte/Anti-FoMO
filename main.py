from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import requests
import os

app = FastAPI()
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"

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

def recommend_playlist():
    access_token = get_spotify_access_token()
    headers = {"Authorization": f"Bearer {access_token}"}
    playlist_id = "37i9dQZF1DXcBWIGoYBM5M"
    playlist_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    response = requests.get(playlist_url, headers=headers)
    
    if response.status_code == 200:
        playlist = response.json()
        playlist_name = playlist["name"]
        return f"推薦播放清單：{playlist_name}"
    else:
        return "無法推薦播放清單。"

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
            
            if "推薦歌曲" in text:
                reply_text = search_song("love")
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
            elif "推薦播放清單" in text:
                reply_text = recommend_playlist()
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
    
    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
