import hashlib


def normalize_sm2_public_key(public_key: str) -> str:
    normalized = public_key.strip()
    return normalized if normalized.startswith("04") else f"04{normalized}"


def encrypt_sms_code(*, public_key: str, sms_code: str) -> str:
    code = sms_code.strip()
    if public_key.startswith("MOCK-"):
        return hashlib.sha256(f"{public_key}:{code}".encode()).hexdigest()

    from jyd_loan.utils.message import sm2

    crypt_sm2 = sm2.CryptSM2(None, normalize_sm2_public_key(public_key), mode=1)
    return crypt_sm2.encrypt(code.encode()).hex()
