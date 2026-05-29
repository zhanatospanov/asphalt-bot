"""Управление доступом."""
import os

# Telegram user_id тех, кто может работать с ботом
# Задаются через переменные среды: ADMIN_IDS, WEIGHER_IDS
# Несколько ID разделяются запятой: "123456,789012"


def _parse_ids(env_var: str) -> set[int]:
    raw = os.environ.get(env_var, "")
    if not raw.strip():
        return set()
    try:
        return {int(x.strip()) for x in raw.split(",") if x.strip()}
    except ValueError:
        return set()


def get_admin_ids() -> set[int]:
    return _parse_ids("ADMIN_IDS")


def get_weigher_ids() -> set[int]:
    return _parse_ids("WEIGHER_IDS")


def get_all_allowed() -> set[int]:
    return get_admin_ids() | get_weigher_ids()


def is_admin(user_id: int) -> bool:
    return user_id in get_admin_ids()


def is_allowed(user_id: int) -> bool:
    allowed = get_all_allowed()
    # Если список пуст — разрешаем всем (режим первой настройки)
    if not allowed:
        return True
    return user_id in allowed
