"""Управление покупателями."""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.session import get_session, set_state, get_state, set_temp, get_temp, clear_temp, States
from utils.database import get_buyers, get_buyer, add_buyer
from utils.access import is_allowed


async def cmd_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /покупатель — выбор или добавление покупателя."""
    user_id = update.effective_user.id
    buyers = get_buyers()

    buttons = []
    for b in buyers:
        buttons.append([InlineKeyboardButton(
            f"{b['name']}",
            callback_data=f"buyer_select_{b['id']}"
        )])
    buttons.append([InlineKeyboardButton("➕ Новый покупатель", callback_data="buyer_new")])

    session = get_session(user_id)
    current = f"\n\n✅ Текущий: <b>{session.buyer_name}</b>" if session.buyer_name else ""

    kb = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        f"👤 Выберите покупателя или добавьте нового:{current}",
        parse_mode="HTML",
        reply_markup=kb
    )


async def callback_buyer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "buyer_new":
        set_state(user_id, States.BUYER_NEW_NAME)
        clear_temp(user_id)
        await query.edit_message_text(
            "➕ Введите наименование нового покупателя:"
        )

    elif data.startswith("buyer_select_"):
        buyer_id = int(data.split("_")[-1])
        buyer = get_buyer(buyer_id)
        if not buyer:
            await query.edit_message_text("❌ Покупатель не найден.")
            return

        session = get_session(user_id)
        session.buyer_id = buyer["id"]
        session.buyer_name = buyer["name"]
        session.buyer_bin = buyer.get("bin", "")
        session.buyer_address = buyer.get("address", "")
        set_state(user_id, None)

        await query.edit_message_text(
            f"✅ Покупатель установлен: <b>{buyer['name']}</b>",
            parse_mode="HTML"
        )


async def handle_buyer_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пошаговый ввод нового покупателя."""
    user_id = update.effective_user.id
    state = get_state(user_id)
    text = update.message.text.strip()

    if state == States.BUYER_NEW_NAME:
        set_temp(user_id, "buyer_name", text)
        set_state(user_id, States.BUYER_NEW_BIN)
        await update.message.reply_text(
            f"✅ Наименование: <b>{text}</b>\n\nВведите БИН покупателя\n"
            f"(или отправьте <code>-</code> чтобы пропустить):",
            parse_mode="HTML"
        )

    elif state == States.BUYER_NEW_BIN:
        bin_ = None if text == "-" else text
        set_temp(user_id, "buyer_bin", bin_)
        set_state(user_id, States.BUYER_NEW_ADDRESS)
        await update.message.reply_text(
            "Введите адрес покупателя\n"
            "(или отправьте <code>-</code> чтобы пропустить):",
            parse_mode="HTML"
        )

    elif state == States.BUYER_NEW_ADDRESS:
        address = None if text == "-" else text
        name = get_temp(user_id, "buyer_name")
        bin_ = get_temp(user_id, "buyer_bin")

        buyer_id = add_buyer(name, bin_, address)

        session = get_session(user_id)
        session.buyer_id = buyer_id
        session.buyer_name = name
        session.buyer_bin = bin_
        session.buyer_address = address
        set_state(user_id, None)
        clear_temp(user_id)

        await update.message.reply_text(
            f"✅ Покупатель добавлен и установлен: <b>{name}</b>",
            parse_mode="HTML"
        )
