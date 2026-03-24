import threading
import time
from collections import defaultdict

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60

_attempts = defaultdict(int)
_lockouts = {}
_lock = threading.Lock()


def _normalize(username: str) -> str:
    return (username or "").strip().lower()


def is_locked(username: str) -> bool:
    key = _normalize(username)
    now = time.time()

    with _lock:
        locked_until = _lockouts.get(key)
        if not locked_until:
            return False

        if now >= locked_until:
            _lockouts.pop(key, None)
            _attempts.pop(key, None)
            return False

        return True


def record_failure(username: str):
    key = _normalize(username)

    with _lock:
        _attempts[key] += 1
        if _attempts[key] >= MAX_ATTEMPTS:
            _lockouts[key] = time.time() + LOCKOUT_SECONDS


def reset_attempts(username: str):
    key = _normalize(username)

    with _lock:
        _attempts.pop(key, None)
        _lockouts.pop(key, None)


def get_remaining_lock_time(username: str) -> int:
    key = _normalize(username)
    now = time.time()

    with _lock:
        locked_until = _lockouts.get(key)
        if not locked_until:
            return 0
        return max(0, int(locked_until - now))
