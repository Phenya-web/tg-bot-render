import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

TOKEN = os.getenv("TOKEN")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("Привет! Введите номер курса и номер группы через пробел (например: 2 31)")

@dp.message_handler()
async def handle_input(message: types.Message):
    try:
        course, group = message.text.strip().split()
        if course.isdigit() and group.isdigit():
            await message.reply(f"Спасибо! Вот ссылка на канал: {CHANNEL_LINK}")
        else:
            await message.reply("Ошибка: введите два числа через пробел.")
    except:
        await message.reply("Ошибка формата. Пример: 2 31")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
