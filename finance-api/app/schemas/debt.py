from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DebtDirection


class DebtCreate(BaseModel):
    counterparty: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    direction: DebtDirection
    description: str | None = Field(default=None, max_length=255)
    due_date: date_type | None = None


class DebtUpdate(BaseModel):
    counterparty: str | None = Field(default=None, min_length=1, max_length=120)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    direction: DebtDirection | None = None
    is_settled: bool | None = None
    description: str | None = Field(default=None, max_length=255)
    due_date: date_type | None = None


class DebtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    counterparty: str
    amount: Decimal
    direction: DebtDirection
    is_settled: bool
    description: str | None
    due_date: date_type | None
    created_at: datetime
