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
BOT_NAME = os.environ.get('BOT_NAME', '@小助手')

# --- 初始化設定 ---
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 輔助函式：清理 Markdown 符號 (作為獨立工具，不加裝飾器)
# ==========================================
def clean_markdown_for_line(text):
    text = text.replace("**", "")
    text = text.replace("### ", "")
    text = text.replace("#### ", "")
    text = text.replace("---", "")
    return text.strip()

# ==========================================
# Webhook 接收端點
# ==========================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ==========================================
# 處理 LINE 文字訊息的主邏輯
# ==========================================
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text.strip()
    is_group = event.source.type in ['group', 'room']
    
    # 判斷是否在群組中被 Tag
    if is_group and not user_message.startswith(BOT_NAME):
        return
        
    # 把 Tag 名字濾掉，留下真正的問題
    if user_message.startswith(BOT_NAME):
        user_message = user_message.replace(BOT_NAME, "", 1).strip()
        
    if not user_message:
        return

    try:
        # 1. 將使用者的問題丟給 Gemini
        response = model.generate_content(user_message)
        raw_text = response.text
        
        # 2. 把 Gemini 回傳的原文，丟進清洗機洗乾淨
        clean_text = clean_markdown_for_line(raw_text)
        
        # 3. 把洗乾淨的文字傳回 LINE
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
    app.run(host='0.0.0.0', port=port)        return

    try:
        response = model.generate_content(user_message)
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=response.text)]
                )
            )
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
