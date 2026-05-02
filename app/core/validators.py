from __future__ import annotations

import re


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
PHONE_PATTERN = re.compile(r"^\d{2}-\d{5}\.\d{4}$")
TEAM_PHONE_PATTERN = re.compile(r"^\d{2}-\d{5}-\d{4}$")


def normalize_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf)


def is_valid_cpf(cpf: str) -> bool:
    digits = normalize_cpf(cpf)
    if len(digits) != 11:
        return False
    if digits == digits[0] * 11:
        return False

    numbers = [int(digit) for digit in digits]

    first_sum = sum(numbers[index] * (10 - index) for index in range(9))
    first_digit = (first_sum * 10) % 11
    if first_digit == 10:
        first_digit = 0

    second_sum = sum(numbers[index] * (11 - index) for index in range(10))
    second_digit = (second_sum * 10) % 11
    if second_digit == 10:
        second_digit = 0

    return numbers[9] == first_digit and numbers[10] == second_digit


def validate_and_normalize_cpf(cpf: str) -> str:
    normalized = normalize_cpf(cpf)
    if not is_valid_cpf(normalized):
        raise ValueError("CPF is invalid.")
    return normalized


def validate_phone(phone: str) -> str:
    normalized = phone.strip()
    if not PHONE_PATTERN.fullmatch(normalized):
        raise ValueError("Phone must use the format xx-xxxxx.xxxx.")
    return normalized


def validate_team_phone(phone: str) -> str:
    normalized = phone.strip()
    if not TEAM_PHONE_PATTERN.fullmatch(normalized):
        raise ValueError("Phone must use the format xx-xxxxx-xxxx.")
    return normalized


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Email is invalid.")
    return normalized
