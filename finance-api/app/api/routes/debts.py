from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models.debt import Debt
from app.models.enums import DebtDirection
from app.schemas.debt import DebtCreate, DebtOut, DebtUpdate

router = APIRouter(prefix="/debts", tags=["debts"])


def _get_owned(db, current_user, debt_id) -> Debt:
    debt = db.get(Debt, debt_id)
    if not debt or debt.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Debt not found")
    return debt


@router.get("", response_model=list[DebtOut])
def list_debts(
    db: DbDep,
    current_user: CurrentUser,
    direction: DebtDirection | None = None,
    is_settled: bool | None = None,
):
    stmt = select(Debt).where(Debt.user_id == current_user.id)
    if direction is not None:
        stmt = stmt.where(Debt.direction == direction)
    if is_settled is not None:
        stmt = stmt.where(Debt.is_settled == is_settled)
    return db.scalars(stmt.order_by(Debt.id.desc())).all()


@router.post("", response_model=DebtOut, status_code=201)
def create_debt(data: DebtCreate, db: DbDep, current_user: CurrentUser):
    debt = Debt(user_id=current_user.id, **data.model_dump())
    db.add(debt)
    db.commit()
    db.refresh(debt)
    return debt


@router.patch("/{debt_id}", response_model=DebtOut)
def update_debt(debt_id: int, data: DebtUpdate, db: DbDep, current_user: CurrentUser):
    debt = _get_owned(db, current_user, debt_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(debt, field, val)
    db.commit()
    db.refresh(debt)
    return debt


@router.delete("/{debt_id}", status_code=204)
def delete_debt(debt_id: int, db: DbDep, current_user: CurrentUser):
    debt = _get_owned(db, current_user, debt_id)
    db.delete(debt)
    db.commit()
