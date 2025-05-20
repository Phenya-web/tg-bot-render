import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Получаем токен и ID канала из переменных окружения
TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Пример: -1001234567890 (или @username, если канал публичный)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def send_invite(message: types.Message):
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            creates_join_request=False
        )
        await message.reply(f"🔗 Ваша персональная ссылка на канал:\n{invite.invite_link}")
    except Exception as e:
        await message.reply("❌ Ошибка при создании ссылки. Убедитесь, что бот — админ в канале с нужными правами.")
        print("Ошибка:", e)

@dp.message_handler(commands=['get_id'])
async def get_channel_id(message: types.Message):
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        await message.reply(f"📦 ID канала: `{chat.id}`", parse_mode="Markdown")
    except Exception as e:
        await message.reply("❌ Не удалось получить ID канала.")
        print("Ошибка:", e)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
