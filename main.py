import os
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === НАЛАШТУВАННЯ ===
# Замініть на свій реальний токен або залишіть отримання з системних змінних
TOKEN = os.getenv("BOT_TOKEN", "ТВІЙ_ТОКЕН_БІЛЯ_BOTFATHER")
# Username вашого каналу (бот має бути адміном у цьому каналі!)
CHANNEL_ID = "@твій_канал" 
# Ваше партнерське посилання (наприклад, Binance / Bybit)
REFERRAL_LINK = "https://your-ref-link.com"

# Функція парсингу новин
def get_latest_news():
    url = "https://minfin.com.ua/blogs/"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        title_element = soup.find("a", class_="title")
        if title_element:
            return title_element.text.strip()
    except Exception as e:
        print(f"Помилка парсингу: {e}")
    return None

# Команда /post для перевірки автопостингу вручну
async def post_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_title = get_latest_news()
    if news_title:
        post_text = (
            f"📌 <b>Головне на цей час:</b>\n\n"
            f"{news_title}\n\n"
            f"💡 <i>Слідкуйте за оновленнями та торгуйте на перевірених платформах:</i>\n"
            f"👉 <a href='{REFERRAL_LINK}'>Зареєструватися та отримати бонус</a>"
        )
        await context.bot.send_message(
            chat_id=CHANNEL_ID, 
            text=post_text, 
            parse_mode="HTML"
        )
        await update.message.reply_text("Пост успішно надіслано в канал!")
    else:
        await update.message.reply_text("Не вдалося отримати новини.")

# Основний запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("post", post_to_channel))
    print("Бот запущений...")
    app.run_polling()
