"""Управление доступом — через БД + ADMIN_IDS из env."""
import os


def get_admin_ids() -> set:
    raw = os.environ.get("ADMIN_IDS", "")
    if not raw.strip():
        return set()
    try:
        return {int(x.strip()) for x in raw.split(",") if x.strip()}
    except ValueError:
        return set()


def is_admin(user_id: int) -> bool:
    return user_id in get_admin_ids()


def is_allowed(user_id: int) -> bool:
    # Администраторы всегда разрешены
    if is_admin(user_id):
        return True
    # Остальные — проверяем в БД
    try:
        from utils.database import is_user_allowed
        return is_user_allowed(user_id)
    except Exception:
        return False
