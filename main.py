from linebot import LineBotApi
from linebot.models import TextSendMessage
from fastapi import FastAPI, Request
import os

app = FastAPI()
line_bot_api = LineBotApi('YOUR_CHANNEL_ACCESS_TOKEN')

@app.post("/callback")
async def callback(request: Request):
    body = await request.json()
    events = body.get("events", [])

    for event in events:
        if event["type"] == "message" and event["message"]["type"] == "text":
            text = event["message"]["text"]
            if "連接spotify" in text:
                auth_url = generate_spotify_auth_url()
                reply_text = f"請點擊以下連結以連接你的Spotify帳戶: {auth_url}"
                await line_bot_api.reply_message(event["replyToken"], TextSendMessage(text=reply_text))
            elif "取得spotify資訊" in text:
                # You need to handle storing and retrieving the user's access token
                access_token = get_user_access_token(event["source"]["userId"])
                if access_token:
                    user_info = get_spotify_user_info(access_token)
                    if user_info:
                        reply_text = f"你的Spotify帳戶資訊: {user_info}"
                    else:
                        reply_text = "無法取得Spotify資訊。"
                else:
                    reply_text = "請先連接你的Spotify帳戶。"
                await line_bot_api.reply_message(event["replyToken"], TextSendMessage(text=reply_text))

def generate_spotify_auth_url():
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")
    scope = "user-read-private user-read-email"
    auth_url = "https://accounts.spotify.com/authorize"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": redirect_uri,
    }
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return url

def get_user_access_token(user_id):
    # Implement this function to retrieve the user's access token from your database
    pass

def get_spotify_user_info(access_token):
    user_info_url = "https://api.spotify.com/v1/me"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get(user_info_url, headers=headers)
    if response.status_code != 200:
        return None
    return response.json()
