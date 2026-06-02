import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import google.generativeai as genai

app = Flask(__name__)

# --- 抓取環境變數 ---
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
BOT_NAME = os.environ.get('BOT_NAME', '@Gemini')

# --- 白名單設定 ---
# 從環境變數抓取名單，並切成陣列。例如："U123,C456" -> ['U123', 'C456']
ALLOWED_LIST_STR = os.environ.get('ALLOWED_LIST', '')
ALLOWED_LIST = [x.strip() for x in ALLOWED_LIST_STR.split(',')] if ALLOWED_LIST_STR else []

# --- 初始化設定 ---
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.1-flash-lite') # 請確認你要使用的模型版本

def clean_markdown_for_line(text):
    text = text.replace("**", "")
    text = text.replace("### ", "")
    text = text.replace("#### ", "")
    text = text.replace("---", "")
    return text.strip()

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 1. 抓取這則訊息的「來源身分證字號」
    if event.source.type == 'group':
        chat_id = event.source.group_id
    elif event.source.type == 'room':
        chat_id = event.source.room_id
    else:
        chat_id = event.source.user_id

    # 2. 印出 ID 讓我們可以在 Render 後台的 Logs 偷看
    print(f"========== 安全檢查 ==========")
    print(f"收到訊息！目前的 Chat ID 是: {chat_id}")
    print(f"==============================")

    # 3. 保鑣攔截邏輯：如果我們有設定白名單，且這個 ID 不在名單內，就拒絕服務
    if ALLOWED_LIST and chat_id not in ALLOWED_LIST:
        print(f"⛔ 警告：非白名單用戶 ({chat_id}) 嘗試對話，已封鎖請求。")
        return

    # --- 以下為原本的問答邏輯 ---
    user_message = event.message.text.strip()
    is_group = event.source.type in ['group', 'room']
    
    if is_group and not user_message.startswith(BOT_NAME):
        return
        
    if user_message.startswith(BOT_NAME):
        user_message = user_message.replace(BOT_NAME, "", 1).strip()
        
    if not user_message:
        return

    try:
        response = model.generate_content(user_message)
        clean_text = clean_markdown_for_line(response.text)
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=clean_text)]
                )
            )
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
