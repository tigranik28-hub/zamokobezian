import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
import schedule
from datetime import datetime

# Замените на токен вашего бота
TOKEN = "8400621308:AAESj1JppPadskgEW9HFxZX1AusrqwDun_4"
bot = telebot.TeleBot(TOKEN)

# Хранилище данных пользователей
# user_id -> {'posts_done': int, 'last_date': str (YYYY-MM-DD)}
user_data = {}

# --- Вспомогательные функции ---
def get_today_str():
    return datetime.now().strftime("%Y-%m-%d")

def reset_user_if_needed(user_id):
    """Сбрасывает счётчик пользователя, если наступил новый день"""
    today = get_today_str()
    if user_id not in user_data:
        user_data[user_id] = {'posts_done': 0, 'last_date': today}
    else:
        if user_data[user_id]['last_date'] != today:
            user_data[user_id]['posts_done'] = 0
            user_data[user_id]['last_date'] = today
            # Отправляем уведомление о начале нового дня (опционально)
            bot.send_message(user_id, "Новый день! Напоминания о постах возобновлены.")

def send_reminder_to_user(user_id):
    """Отправляет напоминание конкретному пользователю, если он ещё не сделал 2 поста"""
    reset_user_if_needed(user_id)
    if user_data[user_id]['posts_done'] < 2:
        # Создаём кнопку
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Пост сделан", callback_data="post_done"))
        bot.send_message(
            user_id,
            "Напоминание: нужно сделать два поста в канал.\n"
            "Нажмите кнопку после каждого сделанного поста.",
            reply_markup=markup
        )

def periodic_reminders():
    """Задача, запускаемая каждый час: отправляет напоминания всем активным пользователям"""
    for user_id in list(user_data.keys()):
        try:
            send_reminder_to_user(user_id)
        except Exception as e:
            print(f"Ошибка отправки напоминания пользователю {user_id}: {e}")

def daily_reset():
    """Сбрасывает счётчики для всех пользователей в полночь"""
    today = get_today_str()
    for user_id, data in user_data.items():
        data['posts_done'] = 0
        data['last_date'] = today
    print(f"Ежедневный сброс выполнен для {len(user_data)} пользователей.")

# --- Планировщик ---
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- Обработчики команд и callback'ов ---
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    reset_user_if_needed(user_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📝 Пост сделан", callback_data="post_done"))
    bot.send_message(
        user_id,
        "Привет! Я буду напоминать тебе каждый час о необходимости сделать два поста.\n"
        "После каждого поста нажимай кнопку. После двух нажатий я замолчу до завтра.\n"
        "Чтобы начать, просто жди напоминаний.",
        reply_markup=markup
    )
    # Сразу отправим первое напоминание (опционально)
    send_reminder_to_user(user_id)

@bot.callback_query_handler(func=lambda call: call.data == "post_done")
def handle_post_done(call):
    user_id = call.from_user.id
    reset_user_if_needed(user_id)
    current = user_data[user_id]['posts_done']
    if current >= 2:
        bot.answer_callback_query(call.id, "Ты уже сделал два поста на сегодня! Завтра новый день 😊")
        return
    # Увеличиваем счётчик
    user_data[user_id]['posts_done'] += 1
    remaining = 2 - user_data[user_id]['posts_done']
    if remaining == 0:
        bot.edit_message_text(
            "✅ Отлично! Ты сделал оба поста. Напоминания прекращены до завтра.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, "Спасибо! Сегодня всё. Завтра снова напомню.")
    else:
        bot.edit_message_text(
            f"✅ Пост отмечен! Осталось сделать постов на сегодня: {remaining}\n"
            "Продолжаю напоминать каждый час.",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        bot.answer_callback_query(call.id, f"Отмечено! Осталось {remaining} пост(а).")

# --- Запуск бота и планировщика ---
if __name__ == "__main__":
    # Настраиваем расписание
    schedule.every(1).hours.do(periodic_reminders)        # каждый час
    schedule.every().day.at("00:00").do(daily_reset)      # ежедневный сброс в полночь

    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    @bot.message_handler(commands=['healthcheck'])
def healthcheck_command(message):
    bot.reply_to(message, "OK")
    
    # Запускаем бота
    print("Бот запущен!")
    bot.infinity_polling()
