import os
import datetime
import gspread
import asyncio
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from datetime import timedelta

TOKEN = os.getenv("API_TOKEN")
CHANNEL_1 = os.getenv("CHANNEL_ID")
CHANNEL_2 = os.getenv("CHANNEL_CHAT_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("bot-creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("1G5TYg6CJnEZygfiv6BeKnHuu-XirPQmlT4B2UFn19oc").sheet1

user_states = {}

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.chat.type != 'private':
        await message.reply("Пожалуйста, напиши мне в ЛС.")
        return
    user_id = str(message.from_user.id)

    try:
        records = sheet.get_all_records()
        for row in records:
            if str(row.get("User ID")) == user_id:
                await message.reply("🔁 Вы уже получали ссылку.")
                return
    except Exception as e:
        await message.reply("⚠️ Не удалось проверить таблицу.")
        print("Ошибка чтения Google Sheets:", e)

    unsubscribed = []
    for chat_id in [CHANNEL_1, CHANNEL_2]:
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=int(user_id))
            if member.status not in ['member', 'administrator', 'creator']:
                unsubscribed.append(chat_id)
        except:
            unsubscribed.append(chat_id)

    if not unsubscribed:
        await message.reply("✅ Вы уже подписаны на все каналы.")
        return

    user_states[int(user_id)] = {
        'step': 'wait_name',
        'unsubscribed': unsubscribed
    }
    await message.reply("Здравствуйте! Чтобы получить ссылку, укажите ваши данные.")
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
        await message.reply("👥 Введите номер группы:")
    elif state['step'] == 'wait_group':
        state['group'] = message.text

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

    member = await bot.get_chat_member(chat_id, from_user.id)
    if member.status not in ['administrator', 'creator']:
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Вы должны ответить на сообщение пользователя, которого хотите замутить.")
        return

    target_user = message.reply_to_message.from_user
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.reply("⚠️ Укажите срок мута. Пример: /mute 1h [причина]")
        return
    duration_str = parts[1]
    reason = parts[2] if len(parts) > 2 else None

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

        # Удаление сообщения пользователя
        try:
            await bot.delete_message(chat_id, message.reply_to_message.message_id)
        except Exception as e:
            print("Не удалось удалить сообщение:", e)

        name = f"@{target_user.username}" if target_user.username else f"id {target_user.id}"
        text = f"🔇 {name} замучен на {duration_str}."
        if reason:
            text += f"\nПричина: {reason}"
        await message.reply(text)

    except Exception as e:
        await message.reply("❌ Не удалось замутить пользователя.")
        print("Ошибка mute:", e)
        
@dp.message_handler(commands=['del'])
async def delete_replied_message(message: types.Message):
    if message.chat.type not in ['group', 'supergroup']:
        return

    from_user = message.from_user
    chat_id = message.chat.id

    # Проверка на права администратора
    member = await bot.get_chat_member(chat_id, from_user.id)
    if member.status not in ['administrator', 'creator']:
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Вы должны ответить на сообщение, которое хотите удалить.")
        return

    try:
        # Удаляем сообщение, на которое ответили
        await bot.delete_message(chat_id=chat_id, message_id=message.reply_to_message.message_id)

        # Удаляем саму команду /del
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)

        # Отправляем уведомление и удаляем через 3 секунды
        confirm = await message.answer("Сообщение удалено")
        await asyncio.sleep(3)
        await bot.delete_message(chat_id=chat_id, message_id=confirm.message_id)

    except Exception as e:
        await message.reply("❌ Не удалось удалить сообщение.")
        print("Ошибка при удалении сообщения:", e)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
