import hashlib
import hmac

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def verify_legacy_sha256_password(plain_password: str, hashed_password: str, salt: str) -> bool:
    payload = f"{salt}:{plain_password}"
    legacy_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, hashed_password)