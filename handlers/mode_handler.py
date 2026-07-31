"""Выбор режима смены: асфальт или инертные материалы."""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.session import get_session, set_state, get_state, update_session, States
from utils.database import get_inert_grades, add_inert_grade


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session()
    mode_label = "🔥 Асфальт" if session.mode == "asphalt" else "🪨 Инертные"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Асфальт", callback_data="mode_asphalt")],
        [InlineKeyboardButton("🪨 Инертные материалы", callback_data="mode_inert")],
    ])
    await update.message.reply_text(
        f"Текущий режим: <b>{mode_label}</b>\n\nВыберите тип продукции на смену:",
        parse_mode="HTML",
        reply_markup=kb
    )


async def callback_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "mode_asphalt":
        update_session(mode="asphalt")
        await query.edit_message_text(
            "✅ Режим: <b>🔥 Асфальт</b>\n\nТеперь выберите марку через /grade",
            parse_mode="HTML"
        )
    elif data == "mode_inert":
        update_session(mode="inert")
        await query.edit_message_text(
            "✅ Режим: <b>🪨 Инертные материалы</b>\n\nТеперь выберите материал через /grade",
            parse_mode="HTML"
        )


async def cmd_grade_inert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор инертного материала — вызывается из общего /grade когда mode=inert."""
    user_id = update.effective_user.id
    grades = get_inert_grades()
    session = get_session()
    current = f"\n\n✅ Текущий: <b>{session.asphalt_grade}</b>" if session.asphalt_grade else ""

    buttons = []
    for g in grades:
        buttons.append([InlineKeyboardButton(g["name"], callback_data="inert_" + str(g["id"]))])
    buttons.append([InlineKeyboardButton("➕ Другой материал", callback_data="inert_new")])

    await update.message.reply_text(
        f"🪨 Выберите материал:{current}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def callback_inert_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "inert_new":
        set_state(user_id, "inert_grade_input")
        await query.edit_message_text("Введите название материала:")
        return

    grade_id = int(data.split("_")[1])
    grades = get_inert_grades()
    full_name = next((g["name"] for g in grades if g["id"] == grade_id), None)
    if not full_name:
        await query.edit_message_text("Материал не найден.")
        return

    update_session(asphalt_grade=full_name)
    await query.edit_message_text(
        f"✅ Материал: <b>{full_name}</b>",
        parse_mode="HTML"
    )


async def handle_inert_grade_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    add_inert_grade(text)
    update_session(asphalt_grade=text)
    set_state(user_id, None)
    await update.message.reply_text(
        f"✅ Материал добавлен: <b>{text}</b>",
        parse_mode="HTML"
    )
