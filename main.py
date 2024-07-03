import logging
import os
import re
import sys
from datetime import datetime
import requests
from fastapi import FastAPI, HTTPException, Request
from linebot import (
    LineBotApi, WebhookParser
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage
)
import uvicorn
from dotenv import load_dotenv

if os.getenv('API_ENV') != 'production':
    load_dotenv()

app = FastAPI()

logging.basicConfig(level=os.getenv('LOG', 'WARNING'))
logger = logging.getLogger(__file__)

channel_secret = os.getenv('LINE_CHANNEL_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
if not channel_secret or not channel_access_token:
    logger.error('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

line_bot_api = LineBotApi(channel_access_token)
parser = WebhookParser(channel_secret)

spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')

@app.get("/health")
async def health():
    return 'ok'
    
#推薦歌曲或播放清單
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
                # 使用Spotify API進行歌曲搜索或推薦
                # 可以根據需要自定義相應的邏輯
                reply_text = "這裡是一首不錯的歌曲推薦給你：[歌曲名稱] - [藝人名稱]"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
                
            elif "推薦播放清單" in text:
                # 使用Spotify API進行播放清單推薦
                # 可以根據需要自定義相應的邏輯
                reply_text = "這裡是一個不錯的播放清單推薦給你：[播放清單名稱]"
                await line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))




    return 'OK'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', default=8080))
    debug = True if os.environ.get('API_ENV', default='develop') == 'develop' else False
    logging.info('Application will start...')
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=debug)
