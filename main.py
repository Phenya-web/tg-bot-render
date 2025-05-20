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

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    try:
        invite = await bot.create_chat_invite_link(
            chat_id='@название_твоего_канала_без_ссылки',
            member_limit=1,  # одноразовая ссылка
            creates_join_request=False  # можно изменить, если надо одобрение
        )
        await message.reply(f"Привет! Вот твоя персональная ссылка на канал: {invite.invite_link}")
    except Exception as e:
        await message.reply("❌ Не удалось создать ссылку. Бот должен быть админом канала.")
        print(e)
