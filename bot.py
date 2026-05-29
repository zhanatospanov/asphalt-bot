"""Точка входа Telegram-бота весовой."""
import os
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

from utils.database import init_db
from utils.session import get_state, States
from utils.access import is_allowed

from handlers.trip import (
    cmd_trip, handle_trip_input, callback_trip_confirm
)
from handlers.buyer import (
    cmd_buyer, callback_buyer, handle_buyer_input
)
from handlers.object_handler import (
    cmd_object, callback_object, handle_object_input
)
from handlers.admin import (
    cmd_grade, callback_grade, handle_grade_input,
    cmd_report, callback_report, handle_report_input,
    cmd_company, callback_company, handle_company_input,
    cmd_set_counter, handle_counter_input,
    cmd_temperature, handle_temperature_input, TEMP_STATE,
    cmd_addgrade, handle_addgrade_input, ADDGRADE_STATE,
    cmd_delete, callback_delete,
    cmd_users, callback_users
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]


# ─── Глобальный роутер текстовых сообщений ───────────────────────────────────

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Направляет текстовые сообщения в нужный хэндлер по текущему состоянию FSM."""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id

    if not is_allowed(user_id):
        await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
        return

    state = get_state(user_id)

    # Маппинг состояний → хэндлеры
    if state in (States.TRIP_VEHICLE, States.TRIP_TARE, States.TRIP_GROSS):
        await handle_trip_input(update, context)

    elif state in (States.BUYER_NEW_NAME, States.BUYER_NEW_BIN, States.BUYER_NEW_ADDRESS):
        await handle_buyer_input(update, context)

    elif state in (States.OBJECT_NEW_NAME,):
        await handle_object_input(update, context)

    elif state == States.GRADE_SELECT:
        await handle_grade_input(update, context)

    elif state in (States.REPORT_DATE_FROM, States.REPORT_DATE_TO):
        await handle_report_input(update, context)

    elif state in (States.COMPANY_NAME, States.COMPANY_BIN):
        await handle_company_input(update, context)

    elif state == States.SET_COUNTER:
        await handle_counter_input(update, context)

    elif state == TEMP_STATE:
        await handle_temperature_input(update, context)

    elif state == ADDGRADE_STATE:
        await handle_addgrade_input(update, context)

    else:
        await update.message.reply_text(
            "Используйте команды:\n"
            "/рейс — начать взвешивание\n"
            "/покупатель — выбрать покупателя\n"
            "/марка — выбрать марку асфальта\n"
            "/отчёт — выгрузить журнал в Excel\n"
            "/помощь — список команд"
        )


# ─── /start и /помощь ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    full_name = user.full_name or str(user_id)

    if not is_allowed(user_id):
        for admin_id in get_admin_ids():
            try:
                from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Разрешить " + full_name[:15], callback_data="allow_" + str(user_id)),
                    InlineKeyboardButton("Отклонить", callback_data="deny_" + str(user_id))
                ]])
                lines = ["Запрос доступа:", full_name, "ID: " + str(user_id)]
                if user.username:
                    lines.append("@" + user.username)
                await context.bot.send_message(chat_id=admin_id, text="\n".join(lines), reply_markup=kb)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Admin notify error: {e}", exc_info=True)
        await update.message.reply_text("Запрос отправлен администратору. Ожидайте подтверждения.")
        return

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


# ─── Глобальный фильтр доступа для команд ────────────────────────────────────

async def access_guard(update: Update, context: ContextTypes.DEFAULT_TYPE,
                       handler_func):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        await update.message.reply_text("⛔ У вас нет доступа.")
        return
    await handler_func(update, context)


def guarded(fn):
    async def wrapper(update, context):
        await access_guard(update, context, fn)
    return wrapper


# ─── Роутер callback-кнопок ──────────────────────────────────────────────────

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("trip_"):
        await callback_trip_confirm(update, context)
    elif data.startswith("buyer_"):
        await callback_buyer(update, context)
    elif data.startswith("obj_"):
        await callback_object(update, context)
    elif data.startswith("grade_"):
        await callback_grade(update, context)
    elif data.startswith("report_"):
        await callback_report(update, context)
    elif data.startswith("company_"):
        await callback_company(update, context)
    elif data.startswith("del_"):
        await callback_delete(update, context)
    elif data.startswith("allow_user_") or data.startswith("deny_user_"):
        await callback_user_access(update, context)
    else:
        await query.answer("Неизвестная команда")


# ─── Запуск ──────────────────────────────────────────────────────────────────

def main():
    init_db()
    logger.info("База данных инициализирована")

    app = ApplicationBuilder().token(TOKEN).build()

    # Команды (только латиница — ограничение Telegram Bot API)
    app.add_handler(CommandHandler("start",   guarded(cmd_start)))
    app.add_handler(CommandHandler("help",    guarded(cmd_help)))
    app.add_handler(CommandHandler("trip",    guarded(cmd_trip)))
    app.add_handler(CommandHandler("buyer",   guarded(cmd_buyer)))
    app.add_handler(CommandHandler("obj",     guarded(cmd_object)))
    app.add_handler(CommandHandler("grade",   guarded(cmd_grade)))
    app.add_handler(CommandHandler("report",  guarded(cmd_report)))
    app.add_handler(CommandHandler("company", guarded(cmd_company)))
    app.add_handler(CommandHandler("counter", guarded(cmd_set_counter)))
    app.add_handler(CommandHandler("temp",    guarded(cmd_temperature)))
    app.add_handler(CommandHandler("addgrade", guarded(cmd_addgrade)))
    app.add_handler(CommandHandler("delete",   guarded(cmd_delete)))
    app.add_handler(CommandHandler("users",    guarded(cmd_users)))

    # Callback-кнопки
    app.add_handler(CallbackQueryHandler(callback_router))

    # Текстовые сообщения (FSM)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    # Установка команд в меню Telegram
    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("trip",    "Взвесить машину — новый рейс"),
            BotCommand("buyer",   "Выбрать покупателя"),
            BotCommand("obj",     "Выбрать объект строительства"),
            BotCommand("grade",   "Выбрать марку асфальта"),
            BotCommand("temp",    "Изменить температуру (по умол. 160C)"),
            BotCommand("report",  "Журнал отпуска в Excel"),
            BotCommand("company", "Реквизиты завода (адм.)"),
            BotCommand("counter", "Номер накладной (адм.)"),
            BotCommand("addgrade", "Добавить новую марку асфальта"),
            BotCommand("delete",   "Удалить запись из базы"),
            BotCommand("users",    "Управление пользователями"),
            BotCommand("help",    "Список команд"),
        ])

    app.post_init = post_init

    logger.info("Бот запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()


async def callback_user_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("allow_"):
        user_id = int(data.split("_")[1])
        try:
            from utils.database import add_allowed_user
            chat = await context.bot.get_chat(user_id)
            name = chat.full_name or str(user_id)
            add_allowed_user(user_id, name)
            await query.edit_message_text("Доступ разрешён: " + name)
            await context.bot.send_message(
                chat_id=user_id,
                text="Доступ разрешён! Напишите /start"
            )
        except Exception as e:
            await query.edit_message_text("Ошибка: " + str(e))

    elif data.startswith("deny_"):
        user_id = int(data.split("_")[1])
        await query.edit_message_text("Доступ отклонён для ID: " + str(user_id))
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="В доступе отказано. Обратитесь к администратору."
            )
        except Exception:
            pass
