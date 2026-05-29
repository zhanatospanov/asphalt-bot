"""Управление объектами строительства."""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.session import get_session, set_state, get_state, set_temp, get_temp, clear_temp, States
from utils.database import get_objects, get_object, add_object


async def cmd_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /объект — выбор или добавление объекта."""
    user_id = update.effective_user.id
    objects = get_objects()

    buttons = []
    for o in objects:
        buttons.append([InlineKeyboardButton(
            o["name"], callback_data=f"obj_select_{o['id']}"
        )])
    buttons.append([InlineKeyboardButton("➕ Новый объект", callback_data="obj_new")])

    session = get_session(user_id)
    current = f"\n\n✅ Текущий: <b>{session.object_name}</b>" if session.object_name else ""

    await update.message.reply_text(
        f"🏗 Выберите объект строительства:{current}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def callback_object(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "obj_new":
        set_state(user_id, States.OBJECT_NEW_NAME)
        await query.edit_message_text("➕ Введите наименование объекта:")
        return

    if data.startswith("obj_select_"):
        obj_id = int(data.split("_")[-1])
        obj = get_object(obj_id)
        if not obj:
            await query.edit_message_text("❌ Объект не найден.")
            return

        session = get_session(user_id)
        session.object_id = obj["id"]
        session.object_name = obj["name"]
        set_state(user_id, None)

        await query.edit_message_text(
            f"✅ Объект установлен: <b>{obj['name']}</b>",
            parse_mode="HTML"
        )


async def handle_object_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    obj_id = add_object(text)
    session = get_session(user_id)
    session.object_id = obj_id
    session.object_name = text
    set_state(user_id, None)

    await update.message.reply_text(
        f"✅ Объект добавлен и установлен: <b>{text}</b>",
        parse_mode="HTML"
    )
