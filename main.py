import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

# Конфигурация
TOKEN = os.getenv("API_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Подключение к Google Таблице
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("bot-creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("1G5TYg6CJnEZygfiv6BeKnHuu-XirPQmlT4B2UFn19oc").sheet1

# Память состояний пользователей
user_states = {}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = str(message.from_user.id)

    # Проверка: есть ли уже этот пользователь в таблице
    try:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("User ID")) == user_id:
                await message.reply("🔁 Вы уже получали ссылку. Пожалуйста, используйте ранее выданную.")
                return
    except Exception as e:
        await message.reply("⚠️ Не удалось проверить таблицу.")
        print("Ошибка при проверке таблицы:", e)

    # Проверка: подписан ли пользователь
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=int(user_id))
        if member.status in ['member', 'administrator', 'creator']:
            await message.reply("✅ Вы уже подписаны на канал.")
            return
    except:
        pass

    # Начало сбора данных
    user_states[int(user_id)] = {'step': 'wait_name'}
    await message.reply("📝 Введите ФИО:")

@dp.message_handler(lambda msg: msg.from_user.id in user_states)
async def collect_data(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]

    if state['step'] == 'wait_name':
        state['name'] = message.text
        state['step'] = 'wait_course'
        await message.reply("📚 Введите курс:")
    elif state['step'] == 'wait_course':
        state['course'] = message.text
        state['step'] = 'wait_group'
        await message.reply("👥 Введите номер группы:")
    elif state['step'] == 'wait_group':
        state['group'] = message.text

        # Повторная проверка — нет ли уже этого user_id
        try:
            records = sheet.get_all_records()
            for row in records:
                if str(row.get("User ID")) == str(user_id):
                    await message.reply("🔁 Вы уже получали ссылку. Повторная регистрация невозможна.")
                    user_states.pop(user_id, None)
                    return
        except Exception as e:
            await message.reply("⚠️ Не удалось проверить таблицу повторно.")
            print("Ошибка повторной проверки:", e)

        # Запись в таблицу
        try:
            sheet.append_row([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(user_id),
                state['name'],
                state['course'],
                state['group']
            ])
        except Exception as e:
            await message.reply("⚠️ Не удалось записать в таблицу.")
            print("Ошибка записи:", e)

        # Генерация ссылки
        try:
            invite = await bot.create_chat_invite_link(
                chat_id=CHANNEL_ID,
                member_limit=1,
                creates_join_request=False
            )
            await message.reply(
                f"✅ Спасибо!\n🔗 Ваша персональная ссылка на канал:\n{invite.invite_link}"
            )
        except Exception as e:
            await message.reply("❌ Не удалось создать ссылку.")
            print("Ошибка при создании ссылки:", e)

        user_states.pop(user_id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
