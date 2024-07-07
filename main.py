
import logging
import os
import re
import sys
from datetime import datetime
import requests

if os.getenv('API_ENV') != 'production':
    from dotenv import load_dotenv
    load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction, URIAction,
    FlexSendMessage
)
import uvicorn
#新增的
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
import re


app = Flask(__name__)
logging.basicConfig(level=os.getenv('LOG', 'WARNING'))
logger = logging.getLogger(__file__)

app = FastAPI()

channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
if not channel_secret or not channel_access_token:
    logger.error('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

firebase_url = os.getenv('FIREBASE_URL')
gemini_key = os.getenv('GEMINI_API_KEY')

import google.generativeai as genai
from firebase import firebase
from utils import check_image_quake, check_location_in_message, get_current_weather, get_weather_data, simplify_data

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
        if not isinstance(event.message, TextMessage):
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
                "音樂": 'E',
                "連接spotify": 'F',
                "FoMO": 'G',
                "符合": 'H',
                "其他": 'I'
            }

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
            elif text_condition == 'H' or 'E' or 'F' or 'G' :
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

    return 'OK'
        
        @app.route("/callback", methods=['POST'])
        def callback():
            # get X-Line-Signature header value
            signature = request.headers['X-Line-Signature']
        
            # get request body as text
            body = request.get_data(as_text=True)
            app.logger.info("Request body: " + body)
        
            # handle webhook body
            try:
                handler.handle(body, signature)
            except InvalidSignatureError:
                abort(400)
        
            return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', default=8080))
    debug = True if os.environ.get('API_ENV', default='develop') == 'develop' else False
    logging.info('Application will start...')
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=debug)
