from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SOCIAL_CREDIT_ALPHABET = "0123456789ABCDEFGHJKLMNPQRTUWXY"
SOCIAL_CREDIT_VALUES = {value: index for index, value in enumerate(SOCIAL_CREDIT_ALPHABET)}
SOCIAL_CREDIT_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
IDENTITY_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
IDENTITY_CHECK_CODES = "10X98765432"

SURNAMES = tuple(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元顾孟平黄和穆萧尹姚邵湛汪"
)
GIVEN_CHARS = tuple(
    "子安明远星河嘉木清越景行知夏云舟若溪书宁怀瑾思齐俊彦舒扬雨桐沐阳辰宇一诺语棠锦程"
)
WORD_LEFT = tuple("星云海山林风光明清新嘉华瑞金银玉青蓝紫宏盛恒长远广博智创优卓")
WORD_RIGHT = tuple("河川湖泉峰谷原野城湾桥港庭园坊舍阁轩堂汇联达通科创景航")
PLACE_LEFT = tuple("小新云星月春夏秋冬东南西北上中下前后青绿红金玉百千万")
PLACE_RIGHT = tuple("站店铺屋舍馆坊阁院园庭巷里桥港湾岛谷田庄社汇点")
REGION_CODES = ("110101", "310101", "440106", "510107", "330106", "420106")


@dataclass(frozen=True)
class GeneratedApplicationData:
    environment: str
    customer_no: str
    customer_name: str
    certificate_type: str
    certificate_no: str
    card_no: str
    phone: str
    teller_no: str
    company_name: str
    company_credit_code: str
    organization_code: str


def generate_application_record(
    sequence: int,
    *,
    environment: str,
    birth_date: date,
    gender: str,
    company_type: str,
    teller_no: str = "MOCK",
) -> GeneratedApplicationData:
    if sequence < 0:
        raise ValueError("sequence 不能为负数")
    certificate_no = generate_identity_number(sequence, birth_date, gender)
    credit_code = generate_social_credit_code(sequence)
    return GeneratedApplicationData(
        environment=environment,
        customer_no=f"C{sequence:012d}",
        customer_name=generate_person_name(sequence),
        certificate_type="身份证",
        certificate_no=certificate_no,
        card_no=generate_bank_card_number(sequence),
        phone=f"1{30 + sequence % 70:02d}{sequence % 100_000_000:08d}",
        teller_no=teller_no,
        company_name=generate_company_name(sequence, company_type),
        company_credit_code=credit_code,
        organization_code=credit_code[8:17],
    )


def birth_date_for_age(current_date: date, age: int) -> date:
    try:
        return current_date.replace(year=current_date.year - age)
    except ValueError:
        return current_date.replace(year=current_date.year - age, day=28)


def age_on_date(birth_date: date, current_date: date) -> int:
    return current_date.year - birth_date.year - (
        (current_date.month, current_date.day) < (birth_date.month, birth_date.day)
    )


def generate_person_name(sequence: int) -> str:
    base = len(GIVEN_CHARS)
    value = sequence
    surname = SURNAMES[value % len(SURNAMES)]
    value //= len(SURNAMES)
    given = "".join(GIVEN_CHARS[(value // (base**index)) % base] for index in range(3))
    return surname + given


def generate_company_name(sequence: int, company_type: str) -> str:
    first_count = len(WORD_LEFT) * len(WORD_RIGHT)
    second_count = len(PLACE_LEFT) * len(PLACE_RIGHT)
    first_index = sequence % first_count
    second_index = (sequence // first_count) % second_count
    first = WORD_LEFT[first_index % len(WORD_LEFT)] + WORD_RIGHT[first_index // len(WORD_LEFT)]
    second = (
        PLACE_LEFT[second_index % len(PLACE_LEFT)] + PLACE_RIGHT[second_index // len(PLACE_LEFT)]
    )
    suffix = "公司" if company_type == "91" else "个体"
    return first + second + suffix


def generate_identity_number(sequence: int, birth_date: date, gender: str) -> str:
    order = sequence % 999 + 1
    if gender == "男" and order % 2 == 0:
        order = order + 1 if order < 999 else 997
    if gender == "女" and order % 2 == 1:
        order = order + 1 if order < 999 else 998
    body = f"{REGION_CODES[sequence % len(REGION_CODES)]}{birth_date:%Y%m%d}{order:03d}"
    total = sum(
        int(value) * weight
        for value, weight in zip(body, IDENTITY_WEIGHTS, strict=True)
    )
    return body + IDENTITY_CHECK_CODES[total % 11]


def generate_bank_card_number(sequence: int) -> str:
    body = f"622202{sequence % 1_000_000_000:09d}"
    return body + _luhn_check_digit(body)


def _luhn_check_digit(body: str) -> str:
    total = 0
    parity = (len(body) + 1) % 2
    for index, value in enumerate(body):
        digit = int(value)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def generate_social_credit_code(sequence: int) -> str:
    registration_authority = "9"
    entity_type = "123"[sequence % 3]
    region = REGION_CODES[sequence % len(REGION_CODES)]
    organization = _encode_base31(sequence, 9)
    body = registration_authority + entity_type + region + organization
    check_value = (
        31
        - sum(
            SOCIAL_CREDIT_VALUES[value] * weight
            for value, weight in zip(body, SOCIAL_CREDIT_WEIGHTS, strict=True)
        )
        % 31
    ) % 31
    return body + SOCIAL_CREDIT_ALPHABET[check_value]


def validate_social_credit_code(value: str) -> bool:
    if len(value) != 18 or any(char not in SOCIAL_CREDIT_VALUES for char in value):
        return False
    return value[-1] == generate_social_credit_check_digit(value[:17])


def generate_social_credit_check_digit(body: str) -> str:
    if len(body) != 17:
        raise ValueError("统一社会信用代码本体必须为 17 位")
    total = sum(
        SOCIAL_CREDIT_VALUES[value] * weight
        for value, weight in zip(body, SOCIAL_CREDIT_WEIGHTS, strict=True)
    )
    return SOCIAL_CREDIT_ALPHABET[(31 - total % 31) % 31]


def _encode_base31(value: int, width: int) -> str:
    result = []
    for _ in range(width):
        result.append(SOCIAL_CREDIT_ALPHABET[value % 31])
        value //= 31
    return "".join(reversed(result))
