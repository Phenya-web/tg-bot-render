import os
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from datetime import timedelta

# Telegram bot token и ID каналов
TOKEN = os.getenv("API_TOKEN")
CHANNEL_1 = os.getenv("CHANNEL_ID")
CHANNEL_2 = os.getenv("CHANNEL_CHAT_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("bot-creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("1G5TYg6CJnEZygfiv6BeKnHuu-XirPQmlT4B2UFn19oc").sheet1

user_states = {}  # Временное хранилище шагов


# Проверка — админ ли пользователь
async def is_admin(chat_id, user_id):
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ['administrator', 'creator']


# Команда /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.chat.type != 'private':
    await message.reply("Пожалуйста, напиши мне в ЛС.")
    return
    user_id = str(message.from_user.id)

    # Проверка в таблице — уже есть?
    try:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("User ID")) == user_id:
                await message.reply("🔁 Вы уже получали ссылку. Пожалуйста, используйте ранее выданную.")
                return
    except Exception as e:
        await message.reply("⚠️ Не удалось проверить таблицу.")
        print("Ошибка чтения Google Sheets:", e)

    # Проверка подписки
    unsubscribed = []
    for chat_id in [CHANNEL_1, CHANNEL_2]:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=int(user_id))
            if member.status not in ['member', 'administrator', 'creator']:
                unsubscribed.append(chat_id)
        except Exception as e:
            print(f"Ошибка при проверке {chat_id}:", e)
            unsubscribed.append(chat_id)

    if not unsubscribed:
        await message.reply("✅ Вы уже подписаны на все каналы.")
        return

    # Начинаем опрос
    user_states[int(user_id)] = {
        'step': 'wait_name',
        'unsubscribed': unsubscribed
    }
    await message.reply("Здравствуйте! Чтобы получить ссылку, укажите ваши данные.")
    await message.reply("📝 Введите ФИО:")


# Опрос ФИО, курс, группа
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
        await message.reply("👥 Введите номер группы:")
    elif state['step'] == 'wait_group':
        state['group'] = message.text

        # Повторная проверка на дублирование
        try:
            records = sheet.get_all_records()
            for row in records:
                if str(row.get("User ID")) == str(user_id):
                    await message.reply("Вы уже регистрировались.")
                    user_states.pop(user_id, None)
                    return
        except Exception as e:
            await message.reply("Ошибка при проверке таблицы.")
            print("Повторная проверка:", e)

        # Запись в Google Таблицу
        try:
            sheet.append_row([
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(user_id),
                state['name'],
                state['course'],
                state['group'],
                f"@{message.from_user.username or ''}",
                message.from_user.full_name or ''
            ])
        except Exception as e:
            await message.reply("Ошибка записи в таблицу.")
            print("Ошибка записи:", e)

        # Генерация ссылок
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
                await message.reply("Ошибка при создании ссылки.")
                print("Ошибка ссылки:", e)

        if links:
            text = "\n".join([f"🔗 {link}" for link in links])
            await message.reply(f"✅ Спасибо!\nВот ваши ссылки на каналы:\n{text}")
        else:
            await message.reply("Не удалось создать ссылки.")

        user_states.pop(user_id)


# Команда /mute
@dp.message_handler(commands=['mute'])
async def mute_user(message: types.Message):
    if not message.reply_to_message:
        return await message.reply("⚠️ Используйте /mute в ответ на сообщение.")

    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("🚫 Только администратор может использовать эту команду.")

    args = message.get_args()
    if not args:
        return await message.reply("Укажите длительность: /mute 1h или /mute 3d")

    duration_map = {'h': 'hours', 'd': 'days'}
    try:
        unit = args[-1]
        value = int(args[:-1])
        if unit not in duration_map:
            raise ValueError
        mute_duration = timedelta(**{duration_map[unit]: value})
    except:
        return await message.reply("⚠️ Неверный формат. Пример: /mute 1h")

    user_id = message.reply_to_message.from_user.id
    until_date = datetime.datetime.utcnow() + mute_duration

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user_id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        await message.reply(f"✅ Пользователь заглушён на {value} {duration_map[unit]}")
    except Exception as e:
        await message.reply("❌ Не удалось заглушить пользователя.")
        print("Mute error:", e)


# Команда /unmute
@dp.message_handler(commands=['unmute'])
async def unmute_user(message: types.Message):
    if not message.reply_to_message:
        return await message.reply("⚠️ Используйте /unmute в ответ на сообщение.")

    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply("🚫 Только администратор может использовать эту команду.")

    user_id = message.reply_to_message.from_user.id

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user_id,
            permissions=types.ChatPermissions(can_send_messages=True)
        )
        await message.reply("✅ Пользователь разблокирован.")
    except Exception as e:
        await message.reply("❌ Не удалось разблокировать пользователя.")
        print("Unmute error:", e)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
