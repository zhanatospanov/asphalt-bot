"""
Сессия пользователя — хранится в БД, переживает перезапуски бота.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Session:
    buyer_id:      Optional[int] = None
    buyer_name:    Optional[str] = None
    buyer_bin:     Optional[str] = None
    buyer_address: Optional[str] = None
    object_id:     Optional[int] = None
    object_name:   Optional[str] = None
    asphalt_grade: Optional[str] = None
    temperature:   int = 160
    state:         Optional[str] = None
    temp_data:     dict = field(default_factory=dict)


# RAM-кэш состояний FSM
_states:    dict[int, Optional[str]] = {}
_temp_data: dict[int, dict]          = {}


def _load_session() -> Session:
    """Читает сессию из БД каждый раз — гарантирует актуальность."""
    try:
        from utils.database import get_current_session
        row = get_current_session()
        return Session(
            buyer_id      = row.get("buyer_id"),
            buyer_name    = row.get("buyer_name"),
            buyer_bin     = row.get("buyer_bin"),
            buyer_address = row.get("buyer_address"),
            object_id     = row.get("object_id"),
            object_name   = row.get("object_name"),
            asphalt_grade = row.get("asphalt_grade"),
            temperature   = row.get("temperature") or 160,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Session load error: {e}")
        return Session()


def _persist():
    """Сохраняет текущую сессию в БД."""
    s = _load_session()
    try:
        from utils.database import save_current_session
        save_current_session({
            "buyer_id":      s.buyer_id,
            "buyer_name":    s.buyer_name,
            "buyer_bin":     s.buyer_bin,
            "buyer_address": s.buyer_address,
            "object_id":     s.object_id,
            "object_name":   s.object_name,
            "asphalt_grade": s.asphalt_grade,
            "temperature":   s.temperature,
        })
    except Exception:
        pass


def get_session(user_id: int = 0) -> Session:
    return _load_session()


def set_state(user_id: int, state: Optional[str]):
    _states[user_id] = state


def get_state(user_id: int) -> Optional[str]:
    return _states.get(user_id)


def set_temp(user_id: int, key: str, value):
    if user_id not in _temp_data:
        _temp_data[user_id] = {}
    _temp_data[user_id][key] = value


def get_temp(user_id: int, key: str, default=None):
    return _temp_data.get(user_id, {}).get(key, default)


def clear_temp(user_id: int):
    _temp_data[user_id] = {}


def update_session(**kwargs):
    """Обновляет поля сессии и сохраняет в БД."""
    s = _load_session()
    for k, v in kwargs.items():
        if hasattr(s, k):
            setattr(s, k, v)
    _persist()


class States:
    OBJECT_NEW_NAME  = "object_new_name"
    BUYER_NEW_NAME   = "buyer_new_name"
    BUYER_NEW_BIN    = "buyer_new_bin"
    BUYER_NEW_ADDRESS = "buyer_new_address"
    GRADE_SELECT     = "grade_select"
    TRIP_VEHICLE     = "trip_vehicle"
    TRIP_TARE        = "trip_tare"
    TRIP_GROSS       = "trip_gross"
    TRIP_CONFIRM     = "trip_confirm"
    COMPANY_NAME     = "company_name"
    COMPANY_BIN      = "company_bin"
    REPORT_DATE_FROM = "report_date_from"
    REPORT_DATE_TO   = "report_date_to"
    SET_COUNTER      = "set_counter"
