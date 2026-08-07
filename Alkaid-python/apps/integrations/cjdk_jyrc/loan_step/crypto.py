from __future__ import annotations


class Sm2EncryptionError(RuntimeError):
    pass


def normalize_sm2_public_key(public_key: str) -> str:
    normalized = public_key.strip()
    if not normalized:
        raise Sm2EncryptionError("SM2 public_key 为空")
    return normalized if normalized.startswith("04") else f"04{normalized}"


def encrypt_sms_code(*, public_key: str, sms_code: str) -> str:
    code = sms_code.strip()
    if not code:
        raise Sm2EncryptionError("短信验证码为空")

    try:
        from jyd_loan.utils.message import sm2
    except ImportError as exc:
        raise Sm2EncryptionError(
            "当前环境未安装旧项目使用的 jyd_loan.utils.message.sm2；"
            "请把内网已有 SM2 实现接到 loan_step/crypto.py"
        ) from exc

    normalized_key = normalize_sm2_public_key(public_key)
    try:
        crypt_sm2 = sm2.CryptSM2(None, normalized_key, mode=1)
        return crypt_sm2.encrypt(code.encode()).hex()
    except Exception as exc:
        raise Sm2EncryptionError(f"SM2 加密短信验证码失败：{exc}") from exc
