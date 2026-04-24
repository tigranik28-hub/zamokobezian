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
from http.server import HTTPServer, BaseHTTPRequestHandler

# === Telegram ===
TOKEN = "8400621308:AAESj1JppPadskgEW9HFxZX1AusrqwDun_4"
bot = telebot.TeleBot(TOKEN)

# === GitHub ===
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "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")
REPO_OWNER = os.environ.get("REPO_OWNER", "tigranik28-hub")
REPO_NAME = os.environ.get("REPO_NAME", "zamokobezian")
FILE_PATH = "user_stats.json"  # папка на GitHub

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

# ================= РАБОТА С GITHUB =================
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
        print(f"[GitHub] Ошибка чтения: {response.status_code}")
        return {}, None

def update_github_file(data, sha=None):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content_str = json.dumps(data, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_str.encode()).decode()
    payload = {
        "message": f"Update stats {datetime.now().isoformat()}",
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
    response = requests.put(GITHUB_API_URL, headers=headers, json=payload)
    if response.status_code in (200, 201):
        print("[GitHub] Сохранено успешно")
    else:
        print(f"[GitHub] Ошибка записи: {response.status_code} - {response.text}")

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
    print(f"[SAVE] Начинаю сохранение для user_id={user_id}")
    try:
        # Получаем все текущие данные из файла
        all_data, current_sha = get_github_file()
        print(f"[SAVE] Текущие данные с GitHub: {all_data}")
        print(f"[SAVE] Текущий SHA файла: {current_sha}")

        # Обновляем данные для текущего пользователя
        all_data[str(user_id)] = user_data_entry
        print(f"[SAVE] Новые данные для записи: {all_data}")

        # Подготавливаем содержимое для записи на GitHub
        content_str = json.dumps(all_data, indent=2, ensure_ascii=False)
        content_b64 = base64.b64encode(content_str.encode()).decode()
        payload = {
            "message": f"Update stats for user {user_id} at {datetime.now()}",
            "content": content_b64,
            "branch": "main"
        }
        # Если файл уже существует, добавляем его SHA в запрос
        if current_sha:
            payload["sha"] = current_sha
            print(f"[SAVE] Использую SHA файла: {current_sha}")

        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.put(GITHUB_API_URL, headers=headers, json=payload)

        print(f"[SAVE] Статус ответа от GitHub API: {response.status_code}")
        if response.status_code in [200, 201]:
            print(f"[SAVE] ✅ Успешно! Данные сохранены.")
        else:
            print(f"[SAVE] ❌ Ошибка! Ответ GitHub: {response.text}")

    except Exception as e:
        print(f"[SAVE] ❌ Критическая ошибка: {e}")

def reset_user_today_if_needed(user_data_entry):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_data_entry.get("today_date") != today:
        user_data_entry["today_posts"] = 0
        user_data_entry["today_date"] = today
    return user_data_entry

# ================= ТЕЛЕГРАМ МЕНЮ =================
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = KeyboardButton("📝 Отметить пост")
    btn2 = KeyboardButton("📊 Статистика за всё время")
    btn3 = KeyboardButton("🔄 Сегодняшние посты")
    markup.add(btn1, btn2, btn3)
    return markup

# ================= КОМАНДЫ И CALLBACK =================
bot = telebot.TeleBot(TOKEN)

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
        bot.reply_to(message, "✅ Ты уже сделал два поста сегодня! Жди завтрашнего дня.", reply_markup=get_main_menu())
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

# ================= ИНЛАЙН-КНОПКА В НАПОМИНАНИЯХ =================
@bot.callback_query_handler(func=lambda call: call.data == "post_done")
def handle_post_done(call):
    user_id = call.from_user.id
    user_data_entry, sha = load_user_data(user_id)
    user_data_entry = reset_user_today_if_needed(user_data_entry)

    if user_data_entry["today_posts"] >= 2:
        bot.answer_callback_query(call.id, "Сегодня уже два поста!", show_alert=False)
        return

    user_data_entry["today_posts"] += 1
    user_data_entry["total_posts"] += 1
    save_user_data(user_id, user_data_entry, sha)

    remaining = 2 - user_data_entry["today_posts"]
    bot.answer_callback_query(call.id, f"Пост отмечен! Осталось {remaining}.")

    if remaining == 0:
        bot.edit_message_text("✅ Оба поста сделаны! Молодец.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.send_message(user_id, "🎉 Сегодня всё. Завтра новый день.", reply_markup=get_main_menu())
    else:
        bot.edit_message_text(f"✅ Пост отмечен! Осталось сегодня: {remaining}",
                              chat_id=call.message.chat.id, message_id=call.message.message_id)

# ================= НАПОМИНАНИЯ ПО ЧАСАМ И СБРОС =================
def send_reminder_to_user(user_id):
    user_data_entry, _ = load_user_data(user_id)
    user_data_entry = reset_user_today_if_needed(user_data_entry)
    if user_data_entry["today_posts"] < 2:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Пост сделан", callback_data="post_done"))
        try:
            bot.send_message(user_id, "⏰ Напоминание: нужно сделать два поста в канал.", reply_markup=markup)
        except Exception as e:
            print(f"Ошибка отправки напоминания {user_id}: {e}")

def periodic_reminders():
    data, _ = get_github_file()
    for user_id_str, entry in data.items():
        # не отправляем если пользователь уже сделал 2 поста сегодня
        today = datetime.now().strftime("%Y-%m-%d")
        if entry.get("today_date") == today and entry.get("today_posts", 0) >= 2:
            continue
        try:
            send_reminder_to_user(int(user_id_str))
        except Exception as e:
            print(f"Ошибка в periodic для {user_id_str}: {e}")

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
        print("Ежедневный сброс выполнен")
    elif changed:
        print("Нет sha, пропускаю сброс")

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# ================= HTTP HEALTHCHECK (с поддержкой HEAD) =================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')

    def do_HEAD(self):
        # Поддержка HEAD-запросов (используется Render и некоторыми мониторами)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        # Отключаем вывод каждого запроса в консоль (замусоривает логи)
        pass

def run_http_server():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"HTTP healthcheck сервер запущен на порту {port}")
    server.serve_forever()

# ================= ЗАПУСК =================
if __name__ == "__main__":
    # Планировщик: каждый час и сброс в полночь
    schedule.every(1).hours.do(periodic_reminders)
    schedule.every().day.at("00:00").do(daily_reset)

    # Поток планировщика
    threading.Thread(target=run_scheduler, daemon=True).start()
    # Поток HTTP-сервера для healthcheck
    threading.Thread(target=run_http_server, daemon=True).start()

    print("Бот запущен. Меню активно, статистика хранится на GitHub.")
    bot.infinity_polling()
