"""
Хранение состояния сессии весовщицы в памяти.
Сессия живёт в рамках процесса бота (сбрасывается при перезапуске).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    # Текущий покупатель на смену
    buyer_id: Optional[int] = None
    buyer_name: Optional[str] = None
    buyer_bin: Optional[str] = None
    buyer_address: Optional[str] = None

    # Текущий объект строительства
    object_id: Optional[int] = None
    object_name: Optional[str] = None

    # Текущая марка асфальта
    asphalt_grade: Optional[str] = None

    # Температура при отгрузке (по умолчанию 160°C)
    temperature: int = 160

    # Состояние FSM для пошагового ввода
    state: Optional[str] = None
    temp_data: dict = field(default_factory=dict)


# Словарь: user_id → Session
_sessions: dict[int, Session] = {}


def get_session(user_id: int) -> Session:
    if user_id not in _sessions:
        _sessions[user_id] = Session()
    return _sessions[user_id]


def clear_session(user_id: int):
    _sessions[user_id] = Session()


def set_state(user_id: int, state: Optional[str]):
    get_session(user_id).state = state


def get_state(user_id: int) -> Optional[str]:
    return get_session(user_id).state


def set_temp(user_id: int, key: str, value):
    get_session(user_id).temp_data[key] = value


def get_temp(user_id: int, key: str, default=None):
    return get_session(user_id).temp_data.get(key, default)


def clear_temp(user_id: int):
    get_session(user_id).temp_data = {}


# Состояния FSM
class States:
    # Объект
    OBJECT_MENU = "object_menu"
    OBJECT_NEW_NAME = "object_new_name"

    # Покупатель
    BUYER_MENU = "buyer_menu"
    BUYER_NEW_NAME = "buyer_new_name"
    BUYER_NEW_BIN = "buyer_new_bin"
    BUYER_NEW_ADDRESS = "buyer_new_address"

    # Марка
    GRADE_SELECT = "grade_select"

    # Рейс
    TRIP_VEHICLE = "trip_vehicle"
    TRIP_TARE = "trip_tare"
    TRIP_GROSS = "trip_gross"
    TRIP_CONFIRM = "trip_confirm"

    # Настройки компании
    COMPANY_NAME = "company_name"
    COMPANY_BIN = "company_bin"
    COMPANY_ADDRESS = "company_address"
    COMPANY_PHONE = "company_phone"
    COMPANY_BANK = "company_bank"
    COMPANY_BIK = "company_bik"
    COMPANY_IBAN = "company_iban"
    COMPANY_DIRECTOR = "company_director"

    # Отчёт
    REPORT_DATE_FROM = "report_date_from"
    REPORT_DATE_TO = "report_date_to"

    # Смена счётчика
    SET_COUNTER = "set_counter"
