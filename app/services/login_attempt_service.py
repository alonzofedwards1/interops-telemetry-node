import time
from collections import defaultdict

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 900  # 15 minutes

attempts = defaultdict(int)
lockouts = {}


def is_locked(username: str) -> bool:
    locked_until = lockouts.get(username)
    if not locked_until:
        return False

    if time.time() > locked_until:
        lockouts.pop(username, None)
        attempts[username] = 0
        return False

    return True


def record_failure(username: str):
    attempts[username] += 1

    if attempts[username] >= MAX_ATTEMPTS:
        lockouts[username] = time.time() + LOCKOUT_SECONDS


def reset_attempts(username: str):
    attempts.pop(username, None)
    lockouts.pop(username, None)


def get_remaining_lock_time(username: str) -> int:
    locked_until = lockouts.get(username)
    if not locked_until:
        return 0
    return max(0, int(locked_until - time.time()))