"""Хэндлер основного рабочего процесса — взвешивание рейса."""
from datetime import datetime, timezone, timedelta

ASTANA_TZ = timezone(timedelta(hours=5))
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.session import get_session, set_state, get_state, set_temp, get_temp, clear_temp, States
from utils.database import get_company, get_next_doc_number, save_trip, update_trip_pdf
from utils.pdf_generator import generate_all_docs

MAX_NET_KG = 150_000  # 150 тонн


async def cmd_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import logging
    log = logging.getLogger(__name__)
    user_id = update.effective_user.id
    session = get_session()
    log.info("TRIP CHECK: buyer_id=%s object=%s grade=%s", session.buyer_id, session.object_name, session.asphalt_grade)

    missing = []
    if not session.buyer_id:
        missing.append("👤 /buyer")
    if not session.object_name:
        missing.append("🏗 /obj")
    if not session.asphalt_grade:
        missing.append("🏷 /grade")

    if missing:
        await update.message.reply_text(
            "Сначала задайте:\n" + "\n".join(missing)
        )
        return

    clear_temp(user_id)
    set_state(user_id, States.TRIP_VEHICLE)
    await update.message.reply_text(
        "Новый рейс\n"
        "Покупатель: " + (session.buyer_name or "") + "\n"
        "Объект: " + (session.object_name or "") + "\n"
        "Марка: " + (session.asphalt_grade or "") + "\n"
        "Температура: " + str(session.temperature) + " C\n\n"
        "Введите гос. номер автомобиля и ФИО водителя:"
    )


async def handle_trip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_state(user_id)
    text = update.message.text.strip()

    if state == States.TRIP_VEHICLE:
        set_temp(user_id, "vehicle", text.upper())
        set_state(user_id, States.TRIP_TARE)
        await update.message.reply_text(
            "Авто: " + text.upper() + "\n\nВведите массу тары (кг):"
        )

    elif state == States.TRIP_TARE:
        try:
            tare = float(text.replace(",", ".").replace(" ", ""))
            if tare <= 0:
                raise ValueError
            set_temp(user_id, "tare", tare)
            set_state(user_id, States.TRIP_GROSS)
            await update.message.reply_text(
                "Тара: " + str(int(tare)) + " кг\n\nВведите массу брутто (кг):"
            )
        except ValueError:
            await update.message.reply_text("Введите число в кг, например: 19500")

    elif state == States.TRIP_GROSS:
        try:
            gross = float(text.replace(",", ".").replace(" ", ""))
            tare = get_temp(user_id, "tare")
            if gross <= tare:
                await update.message.reply_text(
                    "Брутто (" + str(int(gross)) + " кг) должно быть больше тары (" + str(int(tare)) + " кг)"
                )
                return
            net = gross - tare
            set_temp(user_id, "gross", gross)
            set_temp(user_id, "net", net)
            set_state(user_id, States.TRIP_CONFIRM)

            session = get_session()
            vehicle = get_temp(user_id, "vehicle")

            # Предупреждение если нетто > 150 тонн
            if net > MAX_NET_KG:
                await update.message.reply_text(
                    "ВНИМАНИЕ! Масса нетто " + str(round(net/1000, 3)) + " т превышает 150 тонн.\n"
                    "Проверьте правильность данных.\n\n"
                    "Продолжить?",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("Да, продолжить", callback_data="trip_confirm"),
                        InlineKeyboardButton("Отмена", callback_data="trip_cancel"),
                    ]])
                )
                return

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Подтвердить и создать накладную", callback_data="trip_confirm")],
                [InlineKeyboardButton("Отмена", callback_data="trip_cancel")],
            ])

            await update.message.reply_text(
                "Проверьте данные рейса:\n\n"
                "Авто: " + vehicle + "\n"
                "Покупатель: " + (session.buyer_name or "") + "\n"
                "Объект: " + (session.object_name or "") + "\n"
                "Марка: " + (session.asphalt_grade or "") + "\n\n"
                "Тара:   " + str(int(tare)) + " кг\n"
                "Брутто: " + str(int(gross)) + " кг\n"
                "Нетто:  " + str(int(net)) + " кг\n"
                "Температура: " + str(session.temperature) + " C",
                reply_markup=kb
            )
        except ValueError:
            await update.message.reply_text("Введите число в кг, например: 52900")


async def callback_trip_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "trip_cancel":
        set_state(user_id, None)
        clear_temp(user_id)
        await query.edit_message_text("Рейс отменён.")
        return

    session = get_session()
    now = datetime.now(ASTANA_TZ)
    doc_num = get_next_doc_number()

    trip_data = {
        "doc_number":     doc_num,
        "trip_date":      now.strftime("%Y-%m-%d"),
        "trip_time":      now.strftime("%H:%M"),
        "vehicle_number": get_temp(user_id, "vehicle"),
        "driver_name":    get_temp(user_id, "driver") or "",
        "buyer_id":       session.buyer_id,
        "buyer_name":     session.buyer_name,
        "asphalt_grade":  session.asphalt_grade,
        "object_name":    session.object_name,
        "temperature":    session.temperature,
        "tare_kg":        get_temp(user_id, "tare"),
        "gross_kg":       get_temp(user_id, "gross"),
        "net_kg":         get_temp(user_id, "net"),
        "created_by":     user_id,
    }

    trip_id = save_trip(trip_data)
    await query.edit_message_text("Формирую паспорт-накладную № " + str(doc_num) + "...")

    company = get_company()
    buyer = {
        "name":    session.buyer_name,
        "bin":     session.buyer_bin or "",
        "address": session.buyer_address or "",
    }

    pdf_bytes = generate_all_docs(trip_data, company, buyer)

    filename = (
        "Накладная_" + str(doc_num) + "_"
        + now.strftime("%d%m%Y") + "_"
        + str(trip_data["vehicle_number"]) + ".pdf"
    )

    net_kg = trip_data["net_kg"]
    msg = await query.message.reply_document(
        document=pdf_bytes,
        filename=filename,
        caption=(
            "Паспорт-накладная № " + str(doc_num) + "\n"
            + now.strftime("%d.%m.%Y") + "  " + trip_data["trip_time"] + "\n"
            + str(trip_data["vehicle_number"]) + "\n"
            + str(session.buyer_name) + "\n"
            + str(session.object_name) + "\n"
            + "Нетто: " + str(int(net_kg)) + " кг  (" + str(round(net_kg/1000, 3)) + " т)\n\n"
            + "Распечатайте 2 экземпляра (верхний и нижний)"
        )
    )

    if msg.document:
        update_trip_pdf(trip_id, msg.document.file_id)

    set_state(user_id, None)
    clear_temp(user_id)
