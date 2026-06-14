from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


def _get_owned(db, current_user, category_id) -> Category:
    cat = db.get(Category, category_id)
    if not cat or cat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbDep, current_user: CurrentUser):
    return db.scalars(select(Category).where(Category.user_id == current_user.id)).all()


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: DbDep, current_user: CurrentUser):
    cat = Category(user_id=current_user.id, name=data.name, type=data.type)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.patch("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: DbDep, current_user: CurrentUser):
    cat = _get_owned(db, current_user, category_id)
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(cat, field, val)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, db: DbDep, current_user: CurrentUser):
    cat = _get_owned(db, current_user, category_id)
    db.delete(cat)
    db.commit()
