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


@dp.message_handler(commands=['mute'])
async def mute_user(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']:
        return

    chat_id = message.chat.id
    from_user = message.from_user

    # Проверка: админ ли отправитель
    member = await bot.get_chat_member(chat_id, from_user.id)
    if member.status not in ['administrator', 'creator']:
        await message.reply("❌ Только администратор может использовать эту команду.")
        return

    target_user = None
    duration_str = None
    reason = None

    # === Вариант 1: ответ на сообщение ===
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            await message.reply("⚠️ Укажите срок мута. Пример: /mute 1h [причина]")
            return
        duration_str = parts[1]
        reason = parts[2] if len(parts) > 2 else None

    # === Вариант 2: /mute @username 1h [причина] ===
    else:
        parts = message.text.split(maxsplit=3)
        if len(parts) < 3:
            await message.reply("⚠️ Укажите username и срок. Пример: /mute @user 1h [причина]")
            return
        username = parts[1].lstrip("@")
        duration_str = parts[2]
        reason = parts[3] if len(parts) > 3 else None

        try:
            # Получаем информацию о пользователе по username
            user_info = await bot.get_chat_member(chat_id, username)
            target_user = user_info.user
        except Exception as e:
            await message.reply("❌ Не удалось найти пользователя в чате.")
            print("Ошибка поиска по username:", e)
            return

    # Проверка и парсинг времени
    multiplier = {'m': 60, 'h': 3600, 'd': 86400}
    unit = duration_str[-1]
    if unit not in multiplier or not duration_str[:-1].isdigit():
        await message.reply("❌ Неверный формат времени. Пример: 1h, 30m, 2d")
        return

    seconds = int(duration_str[:-1]) * multiplier[unit]
    until_date = message.date + timedelta(seconds=seconds)

    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user.id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        name = f"@{target_user.username}" if target_user.username else f"id {target_user.id}"
        text = f"🔇 {name} замучен на {duration_str}."
        if reason:
            text += f"\nПричина: {reason}"
        await message.reply(text)

    except Exception as e:
        await message.reply("❌ Не удалось замутить пользователя.")
        print("Ошибка mute:", e)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
