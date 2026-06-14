from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OperationType


class TransactionCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    type: OperationType
    category_id: int | None = None
    description: str | None = Field(default=None, max_length=255)
    date: date_type | None = None


class TransactionUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    type: OperationType | None = None
    category_id: int | None = None
    description: str | None = Field(default=None, max_length=255)
    date: date_type | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: Decimal
    type: OperationType
    category_id: int | None
    description: str | None
    date: date_type
    created_at: datetime
