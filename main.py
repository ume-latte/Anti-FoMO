import logging
import os
import re
import sys
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import uvicorn
import requests
from firebase import firebase
import google.generativeai as genai
from utils import check_image_quake, check_location_in_message, get_current_weather, get_weather_data, simplify_data

logging.basicConfig(level=os.getenv('LOG', 'WARNING'))
logger = logging.getLogger(__name__)

# Initialize FastAPI and LineBot
app = FastAPI()

line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))
gemini_key = os.getenv('GEMINI_API_KEY')
# Firebase Configuration
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# Gemini API Configuration
gemini_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=gemini_key)

# Spotify Configuration
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

# Initialize Spotify URLs in Firebase
for index, track_url in enumerate(spotify_tracks, start=1):
    fdb.put('/spotify_tracks', f'track_{index}', track_url)

# FastAPI Health Check
@app.get("/health")
async def health():
    return 'ok'

# LineBot Webhook Handler
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
                if "su3g4u dk vu ej8 " in text:
                    auth_url = generate_spotify_auth_url()
                    reply_text = f"請點擊以下連結以連接你的Spotify帳戶: {auth_url}"
                    await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
                elif "推薦歌曲" in text:
                    reply_text = recommend_song(user_id)
                    await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))

                elif "推薦播放清單" in text:
                    reply_text = recommend_playlist(user_id)
                    await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
                # Add more conditions as needed
            except Exception as e:
                logging.error(f"Error processing event: {e}")
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text="處理請求時發生錯誤，請稍後再試。"))

    return 'OK'
# Initialize Gemini Pro API
genai.configure(api_key=gemini_key)

@app.get("/health")
async def health():
    return 'ok'
    @app.post("/webhooks/line")
async def handle_callback(request: Request):
    signature = request.headers.get('X-Line-Signature')

    # Get request body as text
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent) or not isinstance(event.message, TextMessage):
            continue
        
        text = event.message.text
        user_id = event.source.user_id

        # Keyword filtering
        ignore_keywords = ["什麼是FoMO", "緩解FoMO指南", "FoMO測試", "連接spotify", "推薦歌曲", "推薦播放清單"]
        if any(keyword in text for keyword in ignore_keywords):
            return 'OK'  # Ignore messages containing any of the ignore_keywords

        msg_type = event.message.type
        fdb = firebase.FirebaseApplication(firebase_url, None)

        if event.source.type == 'group':
            user_chat_path = f'chat/{event.source.group_id}'
        else:
            user_chat_path = f'chat/{user_id}'
            chat_state_path = f'state/{user_id}'
        
        chatgpt = fdb.get(user_chat_path, None)

        if msg_type == 'text':
            if chatgpt is None:
                messages = []
            else:
                messages = chatgpt

            bot_condition = {
                "清空": 'A',
                "摘要": 'B',
                "地震": 'C',
                "氣候": 'D',
                "音樂": 'E',
                "連接spotify": 'F',
                "FoMO": 'G',
                "符合": 'H',
                "其他": 'I'
            }

            try:
                model = genai.GenerativeModel('gemini-1.5-pro')
                response = model.generate_content(
                    f'請判斷 {text} 裡面的文字屬於 {bot_condition} 裡面的哪一項？符合條件請回傳對應的英文文字就好，不要有其他的文字與字元。'
                )
                text_condition = re.sub(r'[^A-Za-z]', '', response.text.strip())
                reply_msg = ""

                if text_condition == 'A':
                    fdb.delete(user_chat_path, None)
                    reply_msg = '已清空對話紀錄'
                elif text_condition == 'B':
                    model = genai.GenerativeModel('gemini-pro')
                    response = model.generate_content(
                        f'Summary the following message in Traditional Chinese by less 5 list points. \n{messages}'
                    )
                    reply_msg = response.text
                elif text_condition == 'C':
                    model = genai.GenerativeModel('gemini-pro-vision')
                    OPEN_API_KEY = os.getenv('OPEN_API_KEY')
                    earth_res = requests.get(f'https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/E-A0015-003?Authorization={OPEN_API_KEY}&downloadType=WEB&format=JSON')
                    url = earth_res.json()["cwaopendata"]["Dataset"]["Resource"]["ProductURL"]
                    reply_msg = check_image_quake(url) + f'\n\n{url}'
                elif text_condition in ['E', 'F', 'G', 'H']:
                    reply_msg = '如下'
                elif text_condition == 'I':
                    location_text = '台北市'
                    location = check_location_in_message(location_text)
                    weather_data = get_weather_data(location)
                    simplified_data = simplify_data(weather_data)
                    current_weather = get_current_weather(simplified_data)

                    now = datetime.now()
                    formatted_time = now.strftime("%Y/%m/%d %H:%M:%S")

                    if current_weather is not None:
                        total_info = f'位置: {location}\n氣候: {current_weather["Wx"]}\n降雨機率: {current_weather["PoP"]}\n體感: {current_weather["CI"]}\n現在時間: {formatted_time}'
                        response = model.generate_content(
                            f'請用繁體中文、以精簡並且不要加上任何文字格式（包括粗體斜體還有*號等等）回覆以下的訊息，{text}'
                        )
                        reply_msg = response.text
                else:
                    messages.append({'role': 'user', 'parts': [text]})
                    response = model.generate_content(messages)
                    messages.append({'role': 'model', 'parts': [text]})
                    fdb.put_async(user_chat_path, None, messages)
                    reply_msg = response.text

                await line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=reply_msg)
                )

            except Exception as e:
                logger.error(f"Error processing message: {e}")
    return 'OK'
# Spotify Authorization Callback
@app.get("/callback")
async def spotify_callback(request: Request, code: str):
    try:
        if code:
            token = exchange_code_for_token(code)
            if token:
                # Save access token and associate it with user
                return "Spotify authorization successful! You can now go back to LINE and use Spotify features."
            else:
                return "Authorization failed, please try again."
        else:
            return "Authorization failed, please try again."
    except Exception as e:
        logging.error(f"Error during Spotify callback: {e}")
        return "Authorization failed, please try again."

# Helper functions
def generate_spotify_auth_url():
    SPOTIFY_AUTH_URL = os.getenv('SPOTIFY_AUTH_URL')
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=user-read-private user-read-email"
    return auth_url

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

def recommend_song(user_id):
    user_history = get_user_history(user_id)
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

if __name__ == "__main__":
    port = int(os.environ.get('PORT', default=8080))
    debug = True if os.environ.get('API_ENV', default='develop') == 'develop' else False
    logging.info('Application will start...')
    uvicorn.run(app, host="0.0.0.0", port=port, debug=debug)
