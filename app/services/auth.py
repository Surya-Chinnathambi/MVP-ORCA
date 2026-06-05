"""Password hashing utilities using bcrypt directly.

passlib 1.7.4 is incompatible with bcrypt >=4.x (removed __about__).
We call bcrypt directly; the $2b$ hash format is identical.
"""
import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
