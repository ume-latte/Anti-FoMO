from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookParser
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import random
import logging
import requests
from firebase import firebase

# 初始化 FastAPI 應用
app = FastAPI()

# 初始化日誌
logging.basicConfig(level=logging.INFO)

# 初始化 LINE Bot API 和 Webhook Parser
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
parser = WebhookParser(os.getenv('LINE_CHANNEL_SECRET'))

# Firebase 設定
firebase_url = os.getenv('FIREBASE_URL')
fdb = firebase.FirebaseApplication(firebase_url, None)

# 生成 Spotify 授權 URL
def generate_spotify_auth_url():
    SPOTIFY_AUTH_URL = os.getenv('SPOTIFY_AUTH_URL')
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
    SPOTIFY_AUTH_URL = 'https://accounts.spotify.com/authorize'
    auth_url = f"{SPOTIFY_AUTH_URL}?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=user-read-private user-read-email"
    return auth_url
   

# 定義 exchange_code_for_token 函數
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

# 將歌曲 URL 寫入 Firebase
for index, track_url in enumerate(spotify_tracks, start=1):
    fdb.put('/spotify_tracks', f'track_{index}', track_url)

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
    
    # 從 firebase 中取得 spotify_tracks
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

# 處理 LINE Webhook 請求
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
            except Exception as e:
                logging.error(f"Error processing event: {e}")
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text="處理請求時發生錯誤，請稍後再試。"))

# 處理 Spotify 的回調請求
@app.get("/callback")
async def spotify_callback(request: Request, code: str):
    try:
        if code:
            token = exchange_code_for_token(code)
            if token:
                # 在這裡保存訪問令牌，關聯到用戶
                return "Spotify authorization successful! You can now go back to LINE and use Spotify features."
            else:
                return "Authorization failed, please try again."
        else:
            return "Authorization failed, please try again."
    except Exception as e:
        logging.error(f"Error during Spotify callback: {e}")
        return "Authorization failed, please try again."

# 主程式
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get('PORT', default=8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

import logging
import os
import re
import sys
if os.getenv('API_ENV') != 'production':
    from dotenv import load_dotenv

    load_dotenv()


from fastapi import FastAPI, HTTPException, Request
from datetime import datetime
from linebot.v3.webhook import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    TextMessage)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
)

import uvicorn
import requests

logging.basicConfig(level=os.getenv('LOG', 'WARNING'))
logger = logging.getLogger(__file__)

app = FastAPI()

channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None:
    print('Specify LINE_CHANNEL_SECRET as environment variable.')
    sys.exit(1)
if channel_access_token is None:
    print('Specify LINE_CHANNEL_ACCESS_TOKEN as environment variable.')
    sys.exit(1)

configuration = Configuration(
    access_token=channel_access_token
)

async_api_client = AsyncApiClient(configuration)
line_bot_api = AsyncMessagingApi(async_api_client)
parser = WebhookParser(channel_secret)


import google.generativeai as genai
from firebase import firebase
from utils import check_image_quake, check_location_in_message, get_current_weather, get_weather_data, simplify_data


firebase_url = os.getenv('FIREBASE_URL')
gemini_key = os.getenv('GEMINI_API_KEY')


# Initialize the Gemini Pro API
genai.configure(api_key=gemini_key)


@app.get("/health")
async def health():
    return 'ok'


@app.post("/webhooks/line")
async def handle_callback(request: Request):
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = await request.body()
    body = body.decode()

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        logging.info(event)
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue
        text = event.message.text
        user_id = event.source.user_id

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
                "其他": 'E'
            }

            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(
                f'請判斷 {text} 裡面的文字屬於 {bot_condition} 裡面的哪一項？符合條件請回傳對應的英文文字就好，不要有其他的文字與字元。')
            print('='*10)
            text_condition = re.sub(r'[^A-Za-z]', '', response.text)
            print(text_condition)
            print('='*10)
            if text_condition == 'A':
                fdb.delete(user_chat_path, None)
                reply_msg = '已清空對話紀錄'
            elif text_condition == 'B':
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(
                    f'Summary the following message in Traditional Chinese by less 5 list points. \n{messages}')
                reply_msg = response.text
            elif text_condition == 'C':
                print('='*10)
                print("地震相關訊息")
                print('='*10)
                model = genai.GenerativeModel('gemini-pro-vision')
                OPEN_API_KEY = os.getenv('OPEN_API_KEY')
                earth_res = requests.get(f'https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/E-A0015-003?Authorization={OPEN_API_KEY}&downloadType=WEB&format=JSON')
                url = earth_res.json()["cwaopendata"]["Dataset"]["Resource"]["ProductURL"]
                reply_msg = check_image_quake(url)+f'\n\n{url}'
            elif text_condition == 'D':
                location_text = '台北市'
                location = check_location_in_message(location_text)
                print('Location is: ' + location)
                weather_data = get_weather_data(location)
                simplified_data = simplify_data(weather_data)
                current_weather = get_current_weather(simplified_data)

                print('The Data is: ' + str(current_weather))

                now = datetime.now()
                formatted_time = now.strftime("%Y/%m/%d %H:%M:%S")

                if current_weather is not None:
                    total_info = f'位置: {location}\n氣候: {current_weather["Wx"]}\n降雨機率: {current_weather["PoP"]}\n體感: {current_weather["CI"]}\n現在時間: {formatted_time}'

                response = model.generate_content(
                    f'你現在身處在台灣，相關資訊 {total_info}，我朋友說了「{text}」，請問是否有誇張、假裝的嫌疑？ 回答是或否。')
                reply_msg = response.text
            else:
                # model = genai.GenerativeModel('gemini-pro')
                messages.append({'role': 'user', 'parts': [text]})
                response = model.generate_content(messages)
                messages.append({'role': 'model', 'parts': [text]})
                # 更新firebase中的對話紀錄
                fdb.put_async(user_chat_path, None, messages)
                reply_msg = response.text

            await line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_msg)]
                ))

    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', default=8080))
    debug = True if os.environ.get(
        'API_ENV', default='develop') == 'develop' else False
    logging.info('Application will start...')
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=debug)
