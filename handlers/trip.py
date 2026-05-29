"""Хэндлер основного рабочего процесса — взвешивание рейса."""
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.session import get_session, set_state, get_state, set_temp, get_temp, clear_temp, States
from utils.database import get_company, get_next_doc_number, save_trip, update_trip_pdf
from utils.pdf_generator import generate_all_docs


async def cmd_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /рейс — начало взвешивания."""
    user_id = update.effective_user.id
    session = get_session(user_id)

    missing = []
    if not session.buyer_id:
        missing.append("👤 /покупатель")
    if not session.object_name:
        missing.append("🏗 /объект")
    if not session.asphalt_grade:
        missing.append("🏷 /марка")

    if missing:
        await update.message.reply_text(
            "⚠️ Сначала задайте:\n" + "\n".join(missing)
        )
        return

    clear_temp(user_id)
    set_state(user_id, States.TRIP_VEHICLE)
    await update.message.reply_text(
        f"🚛 Новый рейс\n"
        f"👤 Покупатель: <b>{session.buyer_name}</b>\n"
        f"🏗 Объект: <b>{session.object_name}</b>\n"
        f"🏷 Марка: <b>{session.asphalt_grade}</b>\n"
        f"🌡 Температура: <b>{session.temperature} °C</b>\n\n"
        f"Введите гос. номер автомобиля:",
        parse_mode="HTML"
    )


async def handle_trip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пошаговый ввод данных рейса."""
    user_id = update.effective_user.id
    state = get_state(user_id)
    text = update.message.text.strip()

    if state == States.TRIP_VEHICLE:
        set_temp(user_id, "vehicle", text.upper())
        set_state(user_id, States.TRIP_TARE)
        await update.message.reply_text(
            f"✅ Авто: <b>{text.upper()}</b>\n\nВведите массу тары (кг):",
            parse_mode="HTML"
        )

    elif state == States.TRIP_TARE:
        try:
            tare = float(text.replace(",", ".").replace(" ", ""))
            if tare <= 0:
                raise ValueError
            set_temp(user_id, "tare", tare)
            set_state(user_id, States.TRIP_GROSS)
            await update.message.reply_text(
                f"✅ Тара: <b>{int(tare):,} кг</b>\n\nВведите массу брутто (кг):",
                parse_mode="HTML"
            )
        except ValueError:
            await update.message.reply_text("❌ Введите число в кг, например: 19500")

    elif state == States.TRIP_GROSS:
        try:
            gross = float(text.replace(",", ".").replace(" ", ""))
            tare = get_temp(user_id, "tare")
            if gross <= tare:
                await update.message.reply_text(
                    f"❌ Брутто ({int(gross):,} кг) должно быть больше тары ({int(tare):,} кг)"
                )
                return
            net = gross - tare
            set_temp(user_id, "gross", gross)
            set_temp(user_id, "net", net)
            set_state(user_id, States.TRIP_CONFIRM)

            session = get_session(user_id)
            vehicle = get_temp(user_id, "vehicle")

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Подтвердить и создать накладную", callback_data="trip_confirm")],
                [InlineKeyboardButton("❌ Отмена", callback_data="trip_cancel")],
            ])

            await update.message.reply_text(
                f"📋 <b>Проверьте данные рейса:</b>\n\n"
                f"🚛 Авто:         <code>{vehicle}</code>\n"
                f"👤 Покупатель: {session.buyer_name}\n"
                f"🏗 Объект:      {session.object_name}\n"
                f"🏷 Марка:       {session.asphalt_grade}\n\n"
                f"⚖️ Тара:    <b>{int(tare):>10,} кг</b>\n"
                f"⚖️ Брутто:  <b>{int(gross):>10,} кг</b>\n"
                f"⚖️ Нетто:   <b>{int(net):>10,} кг</b>\n"
                f"🌡 Температура: <b>{session.temperature} °C</b>",
                parse_mode="HTML",
                reply_markup=kb
            )
        except ValueError:
            await update.message.reply_text("❌ Введите число в кг, например: 52900")


async def callback_trip_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "trip_cancel":
        set_state(user_id, None)
        clear_temp(user_id)
        await query.edit_message_text("❌ Рейс отменён.")
        return

    session = get_session(user_id)
    now = datetime.now()
    doc_num = get_next_doc_number()

    trip_data = {
        "doc_number":    doc_num,
        "trip_date":     now.strftime("%Y-%m-%d"),
        "trip_time":     now.strftime("%H:%M"),
        "vehicle_number": get_temp(user_id, "vehicle"),
        "buyer_id":      session.buyer_id,
        "buyer_name":    session.buyer_name,
        "asphalt_grade": session.asphalt_grade,
        "object_name":   session.object_name,
        "temperature":   session.temperature,
        "tare_kg":       get_temp(user_id, "tare"),
        "gross_kg":      get_temp(user_id, "gross"),
        "net_kg":        get_temp(user_id, "net"),
        "created_by":    user_id,
    }

    trip_id = save_trip(trip_data)

    await query.edit_message_text(f"⏳ Формирую паспорт-накладную № {doc_num}...")

    company = get_company()
    buyer = {
        "name":    session.buyer_name,
        "bin":     session.buyer_bin or "",
        "address": session.buyer_address or "",
    }

    pdf_bytes = generate_all_docs(trip_data, company, buyer)

    filename = (
        f"Накладная_{doc_num}_{now.strftime('%d%m%Y')}"
        f"_{trip_data['vehicle_number']}.pdf"
    )

    msg = await query.message.reply_document(
        document=pdf_bytes,
        filename=filename,
        caption=(
            f"📄 Паспорт-накладная № {doc_num}\n"
            f"📅 {now.strftime('%d.%m.%Y')}  {trip_data['trip_time']}\n"
            f"🚛 {trip_data['vehicle_number']}\n"
            f"👤 {session.buyer_name}\n"
            f"🏗 {session.object_name}\n"
            f"⚖️ Нетто: {int(trip_data['net_kg']):,} кг  "
            f"({trip_data['net_kg']/1000:.3f} т)\n\n"
            f"🖨 Распечатайте 2 экземпляра (верхний и нижний)"
        )
    )

    if msg.document:
        update_trip_pdf(trip_id, msg.document.file_id)

    set_state(user_id, None)
    clear_temp(user_id)
