import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Telegram config
TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("bot-creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("1G5TYg6CJnEZygfiv6BeKnHuu-XirPQmlT4B2UFn19oc").sheet1

# Временное хранилище шагов
user_states = {}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id

    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            await message.reply("✅ Вы уже подписаны на канал.")
            return
    except:
        pass

    user_states[user_id] = {'step': 'wait_name'}
    await message.reply("📝 Введите ФИО:")

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = str(message.from_user.id)

    # Проверка: есть ли уже такой user_id в таблице
    try:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("User ID")) == user_id:
                await message.reply("🔁 Вы уже получали ссылку. Пожалуйста, используйте её.")
                return
    except Exception as e:
        await message.reply("⚠️ Не удалось проверить таблицу. Попробуйте позже.")
        print("Ошибка чтения Google Sheets:", e)

    # Проверка подписки
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=int(user_id))
        if member.status in ['member', 'administrator', 'creator']:
            await message.reply("✅ Вы уже подписаны на канал.")
            return
    except:
        pass

    # Если пользователь не найден в таблице и не подписан — начинаем опрос
    user_states[int(user_id)] = {'step': 'wait_name'}
    await message.reply("📝 Введите ФИО:")
