import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import threading
import time
import schedule
from datetime import datetime
import json
import requests
import base64
import os

# === Telegram ===
TOKEN = "8400621308:AAESj1JppPadskgEW9HFxZX1AusrqwDun_4"
bot = telebot.TeleBot(TOKEN)

# === GitHub ===
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "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")
REPO_OWNER = os.environ.get("REPO_OWNER", "tigranik28-hub")
REPO_NAME = os.environ.get("REPO_NAME", "zamokobezian")
FILE_PATH = "main/user_stats.json"  # папка на GitHub
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

# === Работа с GitHub ===
def get_github_file():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(GITHUB_API_URL, headers=headers)
    if response.status_code == 200:
        content = response.json()
        sha = content['sha']
        data = json.loads(base64.b64decode(content['content']).decode())
        return data, sha
    elif response.status_code == 404:
        return {}, None
    else:
        print(f"Ошибка GitHub чтение: {response.status_code}")
        return {}, None

def update_github_file(data, sha=None):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content_str = json.dumps(data, indent=2)
    content_b64 = base64.b64encode(content_str.encode()).decode()
    payload = {
        "message": f"Update stats {datetime.now().isoformat()}",
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
    response = requests.put(GITHUB_API_URL, headers=headers, json=payload)
    if response.status_code in [200, 201]:
        print("GitHub обновлён")
    else:
        print(f"Ошибка GitHub записи: {response.status_code}")

def load_user_data(user_id):
    data, sha = get_github_file()
    user_str = str(user_id)
    if user_str not in data:
        data[user_str] = {
            "total_posts": 0,
            "today_date": datetime.now().strftime("%Y-%m-%d"),
            "today_posts": 0
        }
        update_github_file(data, sha)
        return data[user_str], sha
    return data[user_str], sha

def save_user_data(user_id, user_data_entry, sha):
    all_data, _ = get_github_file()
    all_data[str(user_id)] = user_data_entry
    update_github_file(all_data, sha)

def reset_user_today_if_needed(user_data_entry):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_data_entry["today_date"] != today:
        user_data_entry["today_posts"] = 0
        user_data_entry["today_date"] = today
    return user_data_entry

# === Меню ===
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton("📝 Отметить пост")
    btn2 = KeyboardButton("📊 Статистика за всё время")
    btn3 = KeyboardButton("🔄 Сегодняшние посты")
    markup.add(btn1, btn2, btn3)
    return markup

# === Команды и кнопки меню ===
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    load_user_data(user_id)
    bot.send_message(
        user_id,
        "Привет! Я напоминаю о двух постах в час.\n\n"
        "Используй кнопки внизу:\n"
        "• 📝 Отметить пост – после того, как сделал пост\n"
        "• 📊 Статистика за всё время – всего постов\n"
        "• 🔄 Сегодняшние посты – сколько сделано сегодня",
        reply_markup=get_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "📝 Отметить пост")
def mark_post(message):
    user_id = message.chat.id
    user_data_entry, sha = load_user_data(user_id)
    user_data_entry = reset_user_today_if_needed(user_data_entry)
    
    if user_data_entry["today_posts"] >= 2:
        bot.reply_to(message, "✅ Ты уже сделал два поста сегодня! Завтра новый день.", reply_markup=get_main_menu())
        return
    
    user_data_entry["today_posts"] += 1
    user_data_entry["total_posts"] += 1
    save_user_data(user_id, user_data_entry, sha)
    
    remaining = 2 - user_data_entry["today_posts"]
    if remaining == 0:
        bot.reply_to(message, "🎉 Отлично! Оба поста сделаны. Напоминания прекращены до завтра.", reply_markup=get_main_menu())
    else:
        bot.reply_to(message, f"✅ Пост отмечен! Осталось сегодня: {remaining}.", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "📊 Статистика за всё время")
def total_stats(message):
    user_id = message.chat.id
    user_data_entry, _ = load_user_data(user_id)
    total = user_data_entry.get("total_posts", 0)
    bot.reply_to(message, f"📈 За всё время ты отметил постов: {total}. Так держать!", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "🔄 Сегодняшние посты")
def today_stats(message):
    user_id = message.chat.id
    user_data_entry, _ = load_user_data(user_id)
    user_data_entry = reset_user_today_if_needed(user_data_entry)
    today_posts = user_data_entry["today_posts"]
    remaining = 2 - today_posts
    bot.reply_to(message, f"📅 Сегодня сделано: {today_posts} из 2.\nОсталось: {remaining}", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: True)
def fallback(message):
    bot.reply_to(message, "Пожалуйста, используй кнопки меню.", reply_markup=get_main_menu())

# === Напоминания и сброс ===
def send_reminder_to_user(user_id):
    user_data_entry, _ = load_user_data(user_id)
    user_data_entry = reset_user_today_if_needed(user_data_entry)
    if user_data_entry["today_posts"] < 2:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Пост сделан", callback_data="post_done"))
        bot.send_message(user_id, "⏰ Напоминание: нужно сделать два поста в канал.", reply_markup=markup)

def periodic_reminders():
    data, _ = get_github_file()
    for user_id_str in data.keys():
        try:
            send_reminder_to_user(int(user_id_str))
        except Exception as e:
            print(f"Ошибка напоминания {user_id_str}: {e}")

def daily_reset():
    data, sha = get_github_file()
    today = datetime.now().strftime("%Y-%m-%d")
    changed = False
    for uid, entry in data.items():
        if entry.get("today_date") != today:
            entry["today_posts"] = 0
            entry["today_date"] = today
            changed = True
    if changed and sha:
        update_github_file(data, sha)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# === Callback для инлайн-кнопки ===
@bot.callback_query_handler(func=lambda call: call.data == "post_done")
def handle_post_done(call):
    user_id = call.from_user.id
    user_data_entry, sha = load_user_data(user_id)
    user_data_entry = reset_user_today_if_needed(user_data_entry)
    if user_data_entry["today_posts"] >= 2:
        bot.answer_callback_query(call.id, "Сегодня уже два поста!")
        return
    user_data_entry["today_posts"] += 1
    user_data_entry["total_posts"] += 1
    save_user_data(user_id, user_data_entry, sha)
    remaining = 2 - user_data_entry["today_posts"]
    bot.answer_callback_query(call.id, f"Пост отмечен! Осталось {remaining}.")
    bot.edit_message_text(f"✅ Пост отмечен. Осталось сегодня: {remaining}",
                          chat_id=call.message.chat.id,
                          message_id=call.message.message_id)
    if remaining == 0:
        bot.send_message(user_id, "🎉 Молодец! Оба поста готовы. До завтра.", reply_markup=get_main_menu())

# === HTTP healthcheck для Render ===
from http.server import HTTPServer, BaseHTTPRequestHandler
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/healthcheck':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()
def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"Healthcheck на порту {port}")
    server.serve_forever()

# === Запуск ===
if __name__ == "__main__":
    schedule.every(1).hours.do(periodic_reminders)
    schedule.every().day.at("00:00").do(daily_reset)
    threading.Thread(target=run_scheduler, daemon=True).start()
    threading.Thread(target=run_http_server, daemon=True).start()
    print("Бот запущен с меню и GitHub хранилищем")
    bot.infinity_polling()
