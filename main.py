import logging
import os
import sys
import re
import random
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from linebot.models.events import TextMessageContent
from linebot.models.webhooks import WebhookParser as LineWebhookParser
from linebot.models.webhooks import AsyncApiClient, AsyncMessagingApi, Configuration, ReplyMessageRequest

import requests
from firebase import firebase
import google.generativeai as genai
from utils import check_image_quake, check_location_in_message, get_current_weather, get_weather_data, simplify_data

# Initialize FastAPI
app = FastAPI()

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
if os.getenv('API_ENV') != 'production':
    from dotenv import load_dotenv
    load_dotenv()

# Initialize LINE Bot API and Webhook Parser
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
line_bot_api = LineBotApi(channel_access_token)
parser = LineWebhookParser(channel_secret)

# Initialize Firebase
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# Initialize Gemini API
gemini_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=gemini_key)

# Health check endpoint
@app.get("/health")
async def health():
    return 'ok'

# Handle LINE webhook callback
@app.post("/webhooks/line")
async def handle_line_callback(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            text = event.message.text
            user_id = event.source.user_id

            if event.source.type == 'group':
                user_chat_path = f'chat/{event.source.group_id}'
            else:
                user_chat_path = f'chat/{user_id}'
            
            chatgpt = fdb.get(user_chat_path, None)

            if text.startswith("清空"):
                fdb.delete(user_chat_path)
                reply_msg = '已清空對話紀錄'
            elif text.startswith("摘要"):
                if chatgpt:
                    model = genai.GenerativeModel('gemini-pro')
                    response = model.generate_content(f'Summary the following message in Traditional Chinese by less 5 list points. \n{chatgpt}')
                    reply_msg = response.text
                else:
                    reply_msg = "對話紀錄為空"
            elif text.startswith("地震"):
                model = genai.GenerativeModel('gemini-pro-vision')
                OPEN_API_KEY = os.getenv('OPEN_API_KEY')
                earth_res = requests.get(f'https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/E-A0015-003?Authorization={OPEN_API_KEY}&downloadType=WEB&format=JSON')
                url = earth_res.json()["cwaopendata"]["Dataset"]["Resource"]["ProductURL"]
                reply_msg = check_image_quake(url) + f'\n\n{url}'
            elif text.startswith("氣候"):
                location_text = '台北市'  # Replace with actual location extraction logic
                location = check_location_in_message(location_text)
                weather_data = get_weather_data(location)
                simplified_data = simplify_data(weather_data)
                current_weather = get_current_weather(simplified_data)

                if current_weather:
                    now = datetime.now()
                    formatted_time = now.strftime("%Y/%m/%d %H:%M:%S")
                    total_info = f'位置: {location}\n氣候: {current_weather["Wx"]}\n降雨機率: {current_weather["PoP"]}\n體感: {current_weather["CI"]}\n現在時間: {formatted_time}'
                    reply_msg = total_info.text
                else:
                    reply_msg = "無法取得氣象資料"

            else:
                if chatgpt:
                    messages = [{'role': 'user', 'parts': [text]}]
                    response = genai.GenerativeModel('gemini-pro').generate_content(messages)
                    messages.append({'role': 'model', 'parts': [response.text]})
                    fdb.put_async(user_chat_path, None, messages)
                    reply_msg = response.text
                else:
                    reply_msg = "未知指令"

            await line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=reply_msg)
            )

# Generate Spotify authorization URL
@app.get("/spotify/auth-url")
async def generate_spotify_auth_url():
    SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=user-read-private user-read-email"
    return {'auth_url': auth_url}

# Exchange Spotify authorization code for access token
@app.get("/spotify/callback")
async def spotify_callback(request: Request, code: str):
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

    token_url = "https://accounts.spotify.com/api/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET
    }

    response = requests.post(token_url, headers=headers, data=data)

    if response.status_code == 200:
        return "Spotify authorization successful! You can now go back to LINE and use Spotify features."
    else:
        logging.error(f"Failed to exchange code for token: {response.text}")
        return "Authorization failed, please try again."

# Main application entry point
if __name__ == "__main__":
    import uvicorn
    debug = True if os.environ.get('API_ENV', default='develop') == 'develop' else False
    logging.info('Application will start...')
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port, debug=debug)
