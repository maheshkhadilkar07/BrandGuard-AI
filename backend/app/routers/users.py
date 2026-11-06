from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ADMIN
from app.core.database import get_db
from app.core.deps import require_roles
from app.core.security import hash_password
from app.models import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.services import audit

router = APIRouter(prefix="/users", tags=["User management (admin)"])
admin_only = require_roles(ROLE_ADMIN)


@router.get("", response_model=list[UserOut])
def list_users(admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.organisation_id == admin.organisation_id).order_by(User.id)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.scalar(select(User).where(func.lower(User.email) == data.email.lower())):
        raise HTTPException(400, "An account with this email already exists.")
    u = User(organisation_id=admin.organisation_id, full_name=data.full_name.strip(), email=data.email.lower(),
             password_hash=hash_password(data.password), role=data.role)
    db.add(u)
    db.flush()
    audit.log(db, admin, "user.created", "user", u.id, f"role={u.role}")
    db.commit()
    db.refresh(u)
    return u


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None or u.organisation_id != admin.organisation_id:
        raise HTTPException(404, "User not found.")
    if u.id == admin.id and (data.role not in (None, ROLE_ADMIN) or data.is_active is False):
        raise HTTPException(400, "You cannot demote or deactivate your own account.")
    changes = data.model_dump(exclude_unset=True)
    if "password" in changes:
        u.password_hash = hash_password(changes.pop("password"))
    for k, v in changes.items():
        if v is not None:
            setattr(u, k, v)
    audit.log(db, admin, "user.updated", "user", u.id, ", ".join(sorted(data.model_dump(exclude_unset=True))))
    db.commit()
    db.refresh(u)
    return u
