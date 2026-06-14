from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OperationType


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: OperationType


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    type: OperationType | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: OperationType
