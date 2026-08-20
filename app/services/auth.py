from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash a plaintext password with the recommended Argon2 settings."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches a stored password hash."""
    try:
        return password_hash.verify(password, hashed_password)
    except UnknownHashError:
        return False
