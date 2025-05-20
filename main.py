import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Telegram bot token
TOKEN = os.getenv("API_TOKEN")

# Два ID каналов
CHANNEL_1 = os.getenv("CHANNEL_ID")          # Пример: -1001234567890
CHANNEL_2 = os.getenv("CHANNEL_CHAT_ID")     # Пример: -1009876543210

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Google Sheets API setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("bot-creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("1G5TYg6CJnEZygfiv6BeKnHuu-XirPQmlT4B2UFn19oc").sheet1

# Хранилище шагов
user_states = {}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = str(message.from_user.id)

    # Проверка: уже есть в таблице?
    try:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("User ID")) == user_id:
                await message.reply("🔁 Вы уже получали ссылку. Пожалуйста, используйте ранее выданную.")
                return
    except Exception as e:
        await message.reply("⚠️ Не удалось проверить таблицу.")
        print("Ошибка чтения Google Sheets:", e)

    # Проверка подписки на оба канала
    unsubscribed = []
    for chat_id in [CHANNEL_1, CHANNEL_2]:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=int(user_id))
            if member.status not in ['member', 'administrator', 'creator']:
                unsubscribed.append(chat_id)
        except Exception as e:
            print(f"⚠️ Не удалось проверить канал {chat_id}:", e)
            unsubscribed.append(chat_id)

    # Если подписан — сообщаем
    if not unsubscribed:
        await message.reply("✅ Вы уже подписаны на все каналы.")
        return

    # Начинаем сбор данных
    user_states[int(user_id)] = {
        'step': 'wait_name',
        'unsubscribed': unsubscribed  # Сохраняем, чтобы знать, на какие каналы выдавать ссылку
    }
    await message.reply("Здравствуйте! Для того, чтобы подписаться на канал, укажите ваши данные:")
    await message.reply("📝 Введите ФИО:")

@dp.message_handler(lambda msg: msg.from_user.id in user_states)
async def collect_data(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]

    if state['step'] == 'wait_name':
        state['name'] = message.text
        state['step'] = 'wait_course'
        await message.reply("📚 На каком вы курсе?")
    elif state['step'] == 'wait_course':
        state['course'] = message.text
        state['step'] = 'wait_group'
        await message.reply("👥 Введите номер группы: \nПример: 501-93а")
    elif state['step'] == 'wait_group':
        state['group'] = message.text

        # Повторная проверка на дублирование
        try:
            records = sheet.get_all_records()
            for row in records:
                if str(row.get("User ID")) == str(user_id):
                    await message.reply("Вы уже регистрировались раннее.")
                    user_states.pop(user_id, None)
                    return
        except Exception as e:
            await message.reply("Не удалось проверить таблицу.")
            print("Ошибка повторной проверки:", e)

        # Запись в Google Таблицу
        try:
            sheet.append_row([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(user_id),
                state['name'],
                state['course'],
                state['group']
            ])
        except Exception as e:
            await message.reply("Не удалось записать в таблицу.")
            print("Ошибка записи:", e)

        # Генерация одноразовых ссылок
        links = []
        for chat_id in state.get('unsubscribed', []):
            try:
                invite = await bot.create_chat_invite_link(
                    chat_id=chat_id,
                    member_limit=1,
                    creates_join_request=False
                )
                links.append(invite.invite_link)
            except Exception as e:
                await message.reply("Ошибка при создании ссылок.")
                print("Ошибка при создании ссылки:", e)

        # Отправка всех ссылок
        if links:
            text = "\n".join([f"🔗 {link}" for link in links])
            await message.reply(f"✅ Успешная регистрация!\nСсылки на каналы:\n{text}")
        else:
            await message.reply("Ошибка при создании ссылок.")

        user_states.pop(user_id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
