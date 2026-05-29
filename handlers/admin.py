"""Хэндлеры: марка асфальта, отчёт, настройки компании, счётчик."""
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from utils.session import get_session, set_state, get_state, set_temp, get_temp, clear_temp, States, update_session
from utils.database import (
    get_grades, add_grade, get_company, save_company,
    get_trips, get_trips_today, get_next_doc_number, set_doc_number
)
from utils.excel_report import generate_excel
from utils.access import is_admin


# ═══════════════════════════════════════════════════════════════════════════════
#  Марка асфальта
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    grades = get_grades()

    buttons = []
    for g in grades:
        buttons.append([InlineKeyboardButton(g["name"], callback_data=f"grade_{g['id']}")])
    buttons.append([InlineKeyboardButton("➕ Другая марка", callback_data="grade_new")])

    session = get_session()
    current = f"\n\n✅ Текущая: <b>{session.asphalt_grade}</b>" if session.asphalt_grade else ""

    await update.message.reply_text(
        f"🏷 Выберите марку асфальта на сегодня:{current}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def callback_grade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "grade_new":
        set_state(user_id, States.GRADE_SELECT)
        await query.edit_message_text("Введите марку асфальта:")
        return

    # grade_ID
    try:
        grade_id = int(data.split("_")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("Ошибка выбора марки.")
        return
    grades = get_grades()
    full_name = next((g["name"] for g in grades if g["id"] == grade_id), None)
    if not full_name:
        await query.edit_message_text("Марка не найдена.")
        return

    update_session(asphalt_grade=full_name)
    set_state(user_id, None)
    await query.edit_message_text(
        f"✅ Марка установлена: <b>{full_name}</b>",
        parse_mode="HTML"
    )


async def handle_grade_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    update_session(asphalt_grade=text)
    add_grade(text)
    set_state(user_id, None)
    await update.message.reply_text(
        f"✅ Марка установлена и добавлена в справочник: <b>{text}</b>",
        parse_mode="HTML"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Отчёт
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 За сегодня", callback_data="report_today")],
        [InlineKeyboardButton("📅 За вчера", callback_data="report_yesterday")],
        [InlineKeyboardButton("📅 За период (ввести даты)", callback_data="report_period")],
    ])
    await update.message.reply_text("📊 Выберите период отчёта:", reply_markup=kb)


async def callback_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    if data == "report_today":
        await _send_report(query, today, today)
    elif data == "report_yesterday":
        await _send_report(query, yesterday, yesterday)
    elif data == "report_period":
        set_state(user_id, States.REPORT_DATE_FROM)
        await query.edit_message_text(
            "Введите дату начала периода в формате ДД.ММ.ГГГГ\n"
            "Например: <code>01.06.2025</code>",
            parse_mode="HTML"
        )


async def handle_report_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_state(user_id)
    text = update.message.text.strip()

    def parse_date(s):
        for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    if state == States.REPORT_DATE_FROM:
        d = parse_date(text)
        if not d:
            await update.message.reply_text("❌ Неверный формат. Введите ДД.ММ.ГГГГ")
            return
        set_temp(user_id, "date_from", d)
        set_state(user_id, States.REPORT_DATE_TO)
        await update.message.reply_text("Введите дату конца периода (ДД.ММ.ГГГГ):")

    elif state == States.REPORT_DATE_TO:
        d = parse_date(text)
        if not d:
            await update.message.reply_text("❌ Неверный формат. Введите ДД.ММ.ГГГГ")
            return
        date_from = get_temp(user_id, "date_from")
        set_state(user_id, None)
        clear_temp(user_id)
        await _send_report_msg(update, date_from, d)


async def _send_report(query, date_from, date_to):
    await query.edit_message_text("⏳ Формирую отчёт...")
    trips = get_trips(date_from, date_to)
    company = get_company()

    if not trips:
        await query.message.reply_text(f"📭 Рейсов за период не найдено.")
        return

    excel = generate_excel(trips, date_from, date_to, company.get("name", ""))
    total_net = sum(t["net_kg"] for t in trips) / 1000

    d_from = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d.%m.%Y")
    d_to = datetime.strptime(date_to, "%Y-%m-%d").strftime("%d.%m.%Y")
    period = d_from if d_from == d_to else f"{d_from} — {d_to}"

    await query.message.reply_document(
        document=excel,
        filename=f"Отчёт_{date_from}_{date_to}.xlsx",
        caption=f"📊 Журнал отпуска\n📅 {period}\n🚛 Рейсов: {len(trips)}\n⚖️ Итого нетто: {total_net:.3f} т"
    )


async def _send_report_msg(message_or_update, date_from, date_to):
    await message_or_update.message.reply_text("⏳ Формирую отчёт...")
    trips = get_trips(date_from, date_to)
    company = get_company()

    if not trips:
        await message_or_update.message.reply_text("📭 Рейсов за период не найдено.")
        return

    excel = generate_excel(trips, date_from, date_to, company.get("name", ""))
    total_net = sum(t["net_kg"] for t in trips) / 1000

    d_from = datetime.strptime(date_from, "%Y-%m-%d").strftime("%d.%m.%Y")
    d_to = datetime.strptime(date_to, "%Y-%m-%d").strftime("%d.%m.%Y")
    period = d_from if d_from == d_to else f"{d_from} — {d_to}"

    await message_or_update.message.reply_document(
        document=excel,
        filename=f"Отчёт_{date_from}_{date_to}.xlsx",
        caption=f"📊 Журнал отпуска\n📅 {period}\n🚛 Рейсов: {len(trips)}\n⚖️ Итого нетто: {total_net:.3f} т"
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Настройки компании (только для администраторов)
# ═══════════════════════════════════════════════════════════════════════════════

COMPANY_FIELDS = [
    ("name", "company_name", "Наименование организации"),
    ("bin",  "company_bin",  "БИН"),
]


async def cmd_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    company = get_company()
    lines = ["⚙️ <b>Реквизиты завода:</b>\n"]
    for key, _, label in COMPANY_FIELDS:
        val = company.get(key) or "—"
        lines.append(f"  {label}: {val}")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Изменить реквизиты", callback_data="company_edit")]
    ])
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)


async def callback_company(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not is_admin(user_id):
        return

    set_state(user_id, States.COMPANY_NAME)
    clear_temp(user_id)
    await query.edit_message_text(
        "Введите наименование организации (завода):"
    )


async def handle_company_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    state = get_state(user_id)
    text = update.message.text.strip()

    state_map = {s: (k, lbl) for k, s, lbl in COMPANY_FIELDS}
    next_states = [s for _, s, _ in COMPANY_FIELDS]

    if state not in state_map:
        return

    field_key, label = state_map[state]
    set_temp(user_id, field_key, text if text != "-" else "")

    current_idx = next_states.index(state)
    if current_idx + 1 < len(next_states):
        next_state = next_states[current_idx + 1]
        next_label = [lbl for _, s, lbl in COMPANY_FIELDS if s == next_state][0]
        set_state(user_id, next_state)
        await update.message.reply_text(
            f"✅ {label}: <b>{text}</b>\n\nВведите {next_label}\n"
            f"(или <code>-</code> чтобы пропустить):",
            parse_mode="HTML"
        )
    else:
        # Последнее поле — сохраняем
        data = {k: get_temp(user_id, k) for k, _, _ in COMPANY_FIELDS}
        save_company(data)
        set_state(user_id, None)
        clear_temp(user_id)
        await update.message.reply_text("✅ Реквизиты завода сохранены!")


# ═══════════════════════════════════════════════════════════════════════════════
#  Управление счётчиком накладных
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_set_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    set_state(user_id, States.SET_COUNTER)
    await update.message.reply_text(
        "🔢 Введите новый начальный номер накладной\n"
        "Следующая накладная получит этот номер:"
    )


async def handle_counter_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    try:
        num = int(text)
        if num < 1:
            raise ValueError
        set_doc_number(num - 1)  # set_doc_number сохраняет next = num+1, поэтому -1
        # Исправим: передаём напрямую
        from utils.database import set_doc_number as sdn
        # Нужно установить так, чтобы следующий get_next вернул num
        import sqlite3, os
        db_path = os.environ.get("DB_PATH", "asphalt_bot.db")
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE doc_counter SET current_number=? WHERE id=1", (num,))
        conn.commit()
        conn.close()

        set_state(user_id, None)
        await update.message.reply_text(
            f"✅ Счётчик установлен. Следующая накладная: <b>№ {num}</b>",
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите целое число, например: 245")


# ═══════════════════════════════════════════════════════════════════════════════
#  Температура смеси
# ═══════════════════════════════════════════════════════════════════════════════

TEMP_STATE = "set_temperature"

async def cmd_temperature(update, context):
    from utils.session import get_session
    user_id = update.effective_user.id
    session = get_session()
    set_state(user_id, TEMP_STATE)
    await update.message.reply_text(
        f"🌡 Текущая температура: <b>{session.temperature} °C</b>\n\n"
        f"Введите новое значение (например: <code>155</code>):",
        parse_mode="HTML"
    )

async def handle_temperature_input(update, context):
    from utils.session import get_session
    user_id = update.effective_user.id
    text = update.message.text.strip()
    try:
        t = int(text)
        if not (100 <= t <= 200):
            raise ValueError
        update_session(temperature=t)
        set_state(user_id, None)
        await update.message.reply_text(
            f"✅ Температура установлена: <b>{t} °C</b>",
            parse_mode="HTML"
        )
    except ValueError:
        await update.message.reply_text("❌ Введите число от 100 до 200, например: 160")


# ═══════════════════════════════════════════════════════════════════════════════
#  Добавление новой марки асфальта
# ═══════════════════════════════════════════════════════════════════════════════

ADDGRADE_STATE = "addgrade"

async def cmd_addgrade(update, context):
    user_id = update.effective_user.id
    set_state(user_id, ADDGRADE_STATE)
    await update.message.reply_text(
        "Введите название новой марки асфальта.\n"
        "Она добавится в справочник навсегда:",
        parse_mode="HTML"
    )

async def handle_addgrade_input(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    add_grade(text)
    set_state(user_id, None)
    await update.message.reply_text(
        f"Марка добавлена: <b>{text}</b>",
        parse_mode="HTML"
    )

# ── Добавление новой марки асфальта ──────────────────────────────────────────

ADDGRADE_STATE = "addgrade"


async def cmd_addgrade(update, context):
    user_id = update.effective_user.id
    set_state(user_id, ADDGRADE_STATE)
    await update.message.reply_text(
        "Введите название новой марки.\nОна добавится в справочник навсегда:"
    )


async def handle_addgrade_input(update, context):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    add_grade(text)
    set_state(user_id, None)
    await update.message.reply_text(f"Марка добавлена: <b>{text}</b>", parse_mode="HTML")


# ── Удаление записей из БД ────────────────────────────────────────────────────

async def cmd_delete(update, context):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Покупатели",      callback_data="del_menu_buyers")],
        [InlineKeyboardButton("🏗 Объекты",          callback_data="del_menu_objects")],
        [InlineKeyboardButton("🏷 Марки асфальта",  callback_data="del_menu_grades")],
        [InlineKeyboardButton("🚛 Рейсы (журнал)",  callback_data="del_menu_trips")],
    ])
    await update.message.reply_text("🗑 Что удалить?", reply_markup=kb)


async def callback_delete(update, context):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from utils.database import get_conn, _q
    query = update.callback_query
    await query.answer()
    data = query.data

    def get_rows(table, name_col):
        conn = get_conn()
        c = conn.cursor()
        c.execute(f"SELECT id, {name_col} FROM {table} ORDER BY {name_col}")
        rows = c.fetchall()
        conn.close()
        return rows

    def del_row(table, row_id):
        conn = get_conn()
        c = conn.cursor()
        c.execute(_q(f"DELETE FROM {table} WHERE id=?"), (row_id,))
        conn.commit()
        conn.close()

    # Показать список для удаления
    menus = {
        "del_menu_buyers":  ("buyers",        "name",  "👤 Покупатели"),
        "del_menu_objects": ("objects",        "name",  "🏗 Объекты"),
        "del_menu_grades":  ("asphalt_grades", "name",  "🏷 Марки"),
        "del_menu_trips":   ("trips",          "vehicle_number", "🚛 Рейсы"),
    }

    if data in menus:
        table, col, title = menus[data]
        if table == "trips":
            # для рейсов показываем последние 20
            conn = get_conn()
            c = conn.cursor()
            c.execute(
                "SELECT id, doc_number, trip_date, vehicle_number, buyer_name "
                "FROM trips ORDER BY id DESC LIMIT 20"
            )
            rows = c.fetchall()
            conn.close()
            if not rows:
                await query.edit_message_text("Рейсов нет.")
                return
            buttons = [
                [InlineKeyboardButton(
                    f"№{r[1]} {r[2]} {r[3]} {r[4] or ''}",
                    callback_data=f"del_trips_{r[0]}"
                )] for r in rows
            ]
        else:
            rows = get_rows(table, col)
            if not rows:
                await query.edit_message_text("Список пуст.")
                return
            prefix = data.replace("del_menu_", "del_")
            buttons = [
                [InlineKeyboardButton(f"❌ {r[1]}", callback_data=f"{prefix}_{r[0]}")]
                for r in rows
            ]
        buttons.append([InlineKeyboardButton("« Назад", callback_data="del_back")])
        await query.edit_message_text(
            f"{title} — нажми чтобы удалить:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if data == "del_back":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Покупатели",     callback_data="del_menu_buyers")],
            [InlineKeyboardButton("🏗 Объекты",         callback_data="del_menu_objects")],
            [InlineKeyboardButton("🏷 Марки асфальта", callback_data="del_menu_grades")],
            [InlineKeyboardButton("🚛 Рейсы (журнал)", callback_data="del_menu_trips")],
        ])
        await query.edit_message_text("🗑 Что удалить?", reply_markup=kb)
        return

    # Подтверждение удаления
    tables_map = {
        "del_buyers":  "buyers",
        "del_objects": "objects",
        "del_grades":  "asphalt_grades",
        "del_trips":   "trips",
    }
    for prefix, table in tables_map.items():
        if data.startswith(prefix + "_"):
            row_id = int(data.split("_")[-1])
            del_row(table, row_id)
            await query.edit_message_text(f"Запись удалена.")
            return
