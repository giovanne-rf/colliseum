from __future__ import annotations

from datetime import date


def calculate_age(birth_date: date, reference_date: date | None = None) -> int:
    reference = reference_date or date.today()
    years = reference.year - birth_date.year
    had_birthday = (reference.month, reference.day) >= (birth_date.month, birth_date.day)
    return years if had_birthday else years - 1

