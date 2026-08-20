from app.services.auth import hash_password, verify_password


def test_hash_password_creates_argon2_hash_instead_of_plaintext() -> None:
    password = "password123"

    hashed_password = hash_password(password)

    assert hashed_password != password
    assert hashed_password.startswith("$argon2")


def test_hash_password_uses_a_unique_salt() -> None:
    password = "password123"

    assert hash_password(password) != hash_password(password)


def test_verify_password_accepts_matching_password() -> None:
    password = "password123"
    hashed_password = hash_password(password)

    assert verify_password(password, hashed_password) is True


def test_verify_password_rejects_non_matching_password() -> None:
    hashed_password = hash_password("password123")

    assert verify_password("different-password", hashed_password) is False


def test_verify_password_rejects_unknown_hash_format() -> None:
    assert verify_password("password123", "not-a-password-hash") is False
