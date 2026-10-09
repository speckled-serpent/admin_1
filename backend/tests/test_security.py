from app.security import hash_password, verify_password


def test_password_round_trip() -> None:
    stored = hash_password("devpass")
    assert verify_password("devpass", stored)
    assert not verify_password("wrong-pass", stored)
    assert not verify_password("devpass", "not-a-hash")
