from decimal import Decimal

from pydantic import BaseModel


class BalanceOut(BaseModel):
    income: Decimal
    expense: Decimal
    balance: Decimal


class CategoryStat(BaseModel):
    category_id: int | None
    category_name: str | None
    total: Decimal


class MonthStat(BaseModel):
    month: str        # формат "ГГГГ-ММ", например "2026-06"
    income: Decimal
    expense: Decimal
