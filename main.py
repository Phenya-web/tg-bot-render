@dp.message_handler(commands=['get_id'])
async def get_id(message: types.Message):
    try:
        chat = await bot.get_chat('@название_твоего_канала')
        await message.reply(f"ID канала: `{chat.id}`")
    except Exception as e:
        await message.reply("❌ Не удалось получить ID. Убедись, что бот — админ в канале.")
        print(e)
