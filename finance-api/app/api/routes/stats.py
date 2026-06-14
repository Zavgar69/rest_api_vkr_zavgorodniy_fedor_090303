from datetime import date as date_type
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import case, func, select

from app.api.deps import CurrentUser, DbDep
from app.models.category import Category
from app.models.enums import OperationType
from app.models.transaction import Transaction
from app.schemas.stats import BalanceOut, CategoryStat, MonthStat

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/balance", response_model=BalanceOut)
def balance(
    db: DbDep,
    current_user: CurrentUser,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
):
    def total(op: OperationType) -> Decimal:
        stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == current_user.id, Transaction.type == op
        )
        if date_from is not None:
            stmt = stmt.where(Transaction.date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.date <= date_to)
        return Decimal(db.scalar(stmt))

    income = total(OperationType.income)
    expense = total(OperationType.expense)
    return BalanceOut(income=income, expense=expense, balance=income - expense)


@router.get("/by-category", response_model=list[CategoryStat])
def by_category(
    db: DbDep,
    current_user: CurrentUser,
    type: OperationType = OperationType.expense,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
):
    stmt = (
        select(
            Transaction.category_id,
            Category.name,
            func.coalesce(func.sum(Transaction.amount), 0).label("total"),
        )
        .join(Category, Category.id == Transaction.category_id, isouter=True)
        .where(Transaction.user_id == current_user.id, Transaction.type == type)
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.date <= date_to)
    stmt = stmt.group_by(Transaction.category_id, Category.name).order_by(
        func.sum(Transaction.amount).desc()
    )
    rows = db.execute(stmt).all()
    return [
        CategoryStat(category_id=r[0], category_name=r[1], total=Decimal(r[2])) for r in rows
    ]


@router.get("/by-month", response_model=list[MonthStat])
def by_month(db: DbDep, current_user: CurrentUser):
    # Доходы и расходы, сгруппированные по месяцам (для графика динамики).
    income_sum = func.coalesce(
        func.sum(case((Transaction.type == OperationType.income, Transaction.amount), else_=0)), 0
    )
    expense_sum = func.coalesce(
        func.sum(case((Transaction.type == OperationType.expense, Transaction.amount), else_=0)), 0
    )
    month_col = func.to_char(Transaction.date, "YYYY-MM")
    stmt = (
        select(month_col.label("month"), income_sum.label("income"), expense_sum.label("expense"))
        .where(Transaction.user_id == current_user.id)
        .group_by(month_col)
        .order_by(month_col)
    )
    rows = db.execute(stmt).all()
    return [MonthStat(month=r[0], income=Decimal(r[1]), expense=Decimal(r[2])) for r in rows]
