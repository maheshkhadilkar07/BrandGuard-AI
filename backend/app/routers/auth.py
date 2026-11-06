from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ADMIN, ROLE_CREATOR
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Organisation, User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Self-registration always creates a *Creator*. Only the very first user of a brand-new installation
    becomes the Admin (and creates the organisation). Admins create reviewers and other admins."""
    email = data.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(400, "An account with this email already exists.")
    if db.scalar(select(func.count(Organisation.id))) == 0:
        org = Organisation(name=(data.organisation_name or "My Organisation").strip())
        db.add(org)
        db.flush()
        role = ROLE_ADMIN
    else:
        if data.organisation_id is None:
            raise HTTPException(422, "Please choose your organisation.")
        org = db.get(Organisation, data.organisation_id)
        if org is None:
            raise HTTPException(404, "Organisation not found.")
        role = ROLE_CREATOR
    user = User(organisation_id=org.id, full_name=data.full_name.strip(), email=email,
                password_hash=hash_password(data.password), role=role)
    db.add(user)
    db.flush()
    audit.log(db, user, "user.registered", "user", user.id, f"role={role}")
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role, user.organisation_id), user=user)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been deactivated.")
    audit.log(db, user, "user.login", "user", user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role, user.organisation_id), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """JWTs are stateless: the client discards its token. The logout is recorded in the audit log."""
    audit.log(db, user, "user.logout", "user", user.id)
    db.commit()
