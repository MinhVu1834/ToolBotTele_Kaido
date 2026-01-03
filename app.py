import os
from datetime import datetime
import threading
import time

import requests
import telebot
from flask import Flask, request

# ============ CẤU HÌNH ============

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

REG_LINK = "https://u888h8.com?f=5051573"
WEBAPP_LINK = "https://u888h8.com?f=5051573"  # chưa dùng, để sẵn

# Keep-alive (Render)
ENABLE_KEEP_ALIVE = os.getenv("ENABLE_KEEP_ALIVE", "false").lower() == "true"
PING_URL = os.getenv("PING_URL")
PING_INTERVAL = int(os.getenv("PING_INTERVAL", "300"))  # 300s = 5 phút

# ================== KHỞI TẠO BOT & FLASK ==================

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
server = Flask(__name__)

# State user
# user_state[chat_id] có thể là:
#   "WAITING_USERNAME"
#   {"state":"WAITING_GAME","username":...}
#   {"state":"WAITING_RECEIPT","username":...,"game":...}
#   {"state":"WAITING_AMOUNT","username":...,"game":...,"receipt_file_id":...}
user_state = {}

# Debug get file_id
debug_get_id_mode = set()


# ================== KEEP ALIVE ==================
def keep_alive():
    if not PING_URL:
        print("[KEEP_ALIVE] PING_URL chưa cấu hình, không bật keep-alive.")
        return

    print(f"[KEEP_ALIVE] Bắt đầu ping {PING_URL} mỗi {PING_INTERVAL}s")
    while True:
        try:
            r = requests.get(PING_URL, timeout=10)
            print(f"[KEEP_ALIVE] Ping {PING_URL} -> {r.status_code}")
        except Exception as e:
            print("[KEEP_ALIVE] Lỗi ping:", e)
        time.sleep(PING_INTERVAL)


if ENABLE_KEEP_ALIVE:
    threading.Thread(target=keep_alive, daemon=True).start()


# ================== DEBUG GET FILE_ID ==================
@bot.message_handler(commands=["getid"])
def enable_getid(message):
    chat_id = message.chat.id
    debug_get_id_mode.add(chat_id)
    bot.send_message(
        chat_id,
        "✅ Đã bật chế độ lấy FILE_ID.\n"
        "Bây giờ bạn gửi *ảnh / video / file* vào đây, bot sẽ trả lại FILE_ID.\n\n"
        "Tắt bằng lệnh: /stopgetid",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["stopgetid"])
def disable_getid(message):
    chat_id = message.chat.id
    debug_get_id_mode.discard(chat_id)
    bot.send_message(chat_id, "🛑 Đã tắt chế độ lấy FILE_ID.")


# ================== HELPERS ==================
def reset_flow(chat_id: int):
    user_state[chat_id] = "WAITING_USERNAME"


def start_message(chat_id: int):
    # Không dùng nút chọn — gọn
    text = (
        "🎁 Chào anh! Hiện tại U888 đang có khuyến mãi nạp đầu ạ.\n\n"
        "✅ Anh gửi giúp bot tên tài khoản game dùng để đăng nhập nhé.\n\n"
        f"Nếu chưa có tài khoản, anh đăng ký tại đây rồi gửi giúp bot tên tài khoản nhé: {REG_LINK}"
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")
    reset_flow(chat_id)


def ask_game(chat_id: int, username: str):
    bot.send_message(
        chat_id,
        f"✅ Bot đã nhận: *{username}*\n\n"
        "Anh thường chơi *game gì* (slot / live / thể thao / bắn cá / game bài) ạ?",
        parse_mode="Markdown",
    )


def ask_send_receipt(chat_id: int, username: str, game: str):
    text = (
        f"Okie, bot đã ghi nhận anh muốn chơi: *{game}* ✅\n\n"
        "Giờ anh **chuyển khoản nạp đầu**.\n"
        "Chuyển xong anh **chụp ảnh/biên lai** gửi lại ngay tại đây để bot cộng khuyến mãi tự động cho mình anh nhé."
    )
    bot.send_message(chat_id, text, parse_mode="Markdown")


def ask_amount(chat_id: int):
    bot.send_message(chat_id, "✅ Đã nhận ảnh. Anh nạp *bao nhiêu tiền* (số tiền) để bot đối soát nhanh?", parse_mode="Markdown")


def send_to_admin(chat_id: int, tg_username: str, username: str, game: str, amount: str, receipt_file_id: str):
    time_str = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    caption = (
        "KHÁCH GỬI BIÊN LAI\n\n"
        f"Telegram: {tg_username}\n"
        f"Tài khoản: {username}\n"
        f"Game: {game}\n"
        f"Số tiền: {amount}\n"
    )

    # gửi ảnh trước, caption kèm info
    bot.send_photo(ADMIN_CHAT_ID, receipt_file_id, caption=caption)


# ================== /start & /cancel ==================
@bot.message_handler(commands=["start"])
def handle_start(message):
    chat_id = message.chat.id
    print(">>> /start from:", chat_id)
    start_message(chat_id)


@bot.message_handler(commands=["cancel"])
def handle_cancel(message):
    chat_id = message.chat.id
    user_state[chat_id] = None
    bot.send_message(chat_id, "✅ Đã hủy thao tác. Gõ /start để làm lại.")


# ================== TEXT HANDLER ==================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_text(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()
    print(">>> text:", text, "from", chat_id)

    # Nếu user gõ lệnh, để command handler xử lý (tránh dính vào flow)
    if text.startswith("/"):
        return

    state = user_state.get(chat_id)

    # 1) Chờ username
    if state == "WAITING_USERNAME":
        username = text
        user_state[chat_id] = {"state": "WAITING_GAME", "username": username}
        ask_game(chat_id, username)
        return

    # 2) Chờ game
    if isinstance(state, dict) and state.get("state") == "WAITING_GAME":
        game = text
        username = state.get("username", "")
        user_state[chat_id] = {"state": "WAITING_RECEIPT", "username": username, "game": game}
        ask_send_receipt(chat_id, username, game)
        return

    # 3) Chờ số tiền (sau khi nhận ảnh)
    if isinstance(state, dict) and state.get("state") == "WAITING_AMOUNT":
        amount = text
        username = state.get("username", "(không rõ)")
        game = state.get("game", "(không rõ)")
        receipt_file_id = state.get("receipt_file_id")

        tg_username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else "Không có"

        try:
            send_to_admin(chat_id, tg_username, username, game, amount, receipt_file_id)
            bot.send_message(
                chat_id,
                f"✅ Bot đã nhận đủ thông tin.\n"
                f"• Username: *{username}*\n"
                f"• Game: *{game}*\n"
                f"• Số tiền: *{amount}*\n\n"
                "Bot chuyển admin duyệt và cộng **khuyến mãi nạp đầu** cho mình ngay nhé ❤️",
                parse_mode="Markdown",
            )
        except Exception as e:
            print("Lỗi gửi admin:", e)
            bot.send_message(chat_id, "⚠️ Mình gửi thông tin lên admin bị lỗi. Bạn nhắn CSKH giúp mình nhé ạ.")

        user_state[chat_id] = None
        return

    # Nếu user nhắn lung tung ngoài flow:
    bot.send_message(chat_id, "Bạn gõ /start để bắt đầu nhận khuyến mãi nạp đầu nhé ✅")


# ================== MEDIA HANDLER ==================
@bot.message_handler(content_types=["photo", "document", "video"])
def handle_media(message):
    chat_id = message.chat.id

    # Debug getid
    if chat_id in debug_get_id_mode:
        if message.content_type == "photo":
            file_id = message.photo[-1].file_id
            media_type = "ẢNH"
        elif message.content_type == "video":
            file_id = message.video.file_id
            media_type = "VIDEO"
        else:
            file_id = message.document.file_id
            media_type = "FILE"

        bot.reply_to(message, f"✅ *{media_type} FILE_ID:*\n\n`{file_id}`", parse_mode="Markdown")
        print(f"[GET_FILE_ID] {media_type}: {file_id}")
        return

    state = user_state.get(chat_id)

    # Chỉ nhận ảnh/biên lai khi đang WAITING_RECEIPT
    if not (isinstance(state, dict) and state.get("state") == "WAITING_RECEIPT"):
        # nếu user gửi ảnh sai lúc, nhắc nhẹ
        bot.send_message(chat_id, "Bạn gõ /start để làm đúng quy trình nhận khuyến mãi nạp đầu nhé ✅")
        return

    # Lấy file_id
    if message.content_type == "photo":
        receipt_file_id = message.photo[-1].file_id
    elif message.content_type == "document":
        receipt_file_id = message.document.file_id
    else:
        bot.send_message(chat_id, "Bạn gửi *ảnh/biên lai chuyển khoản* giúp mình nhé ạ.", parse_mode="Markdown")
        return

    # chuyển sang chờ số tiền
    user_state[chat_id] = {
        "state": "WAITING_AMOUNT",
        "username": state.get("username", ""),
        "game": state.get("game", ""),
        "receipt_file_id": receipt_file_id,
    }

    ask_amount(chat_id)


# ================== WEBHOOK FLASK ==================
@server.route("/webhook", methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200


@server.route("/", methods=["GET"])
def home():
    return "Bot is running!", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("Running on port", port)
    server.run(host="0.0.0.0", port=port)
