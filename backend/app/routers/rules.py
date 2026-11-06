"""CRUD routers for the five kinds of stored brand rules. Everyone in the organisation may read;
only Admins may create, change or delete."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ADMIN
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import (ApprovedClaim, ApprovedFact, BrandGuideline, ProhibitedWord, Terminology, User)
from app.schemas import rules as S
from app.services import audit


def make_router(prefix: str, model, schema_in, schema_out, label: str) -> APIRouter:
    r = APIRouter(prefix=prefix, tags=[f"Brand rules – {label}"])

    def get_owned(db: Session, user: User, rule_id: int):
        obj = db.get(model, rule_id)
        if obj is None or obj.organisation_id != user.organisation_id:
            raise HTTPException(404, f"{label} not found.")
        return obj

    @r.get("", response_model=list[schema_out])
    def list_rules(active_only: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        q = select(model).where(model.organisation_id == user.organisation_id)
        if active_only:
            q = q.where(model.is_active.is_(True))
        return db.scalars(q.order_by(model.id)).all()

    @r.post("", response_model=schema_out, status_code=201)
    def create_rule(data: schema_in, admin: User = Depends(require_roles(ROLE_ADMIN)), db: Session = Depends(get_db)):
        obj = model(organisation_id=admin.organisation_id, **data.model_dump())
        db.add(obj)
        db.flush()
        audit.log(db, admin, f"{label}.created", prefix.strip("/"), obj.id)
        db.commit()
        db.refresh(obj)
        return obj

    @r.get("/{rule_id}", response_model=schema_out)
    def read_rule(rule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        return get_owned(db, user, rule_id)

    @r.put("/{rule_id}", response_model=schema_out)
    def update_rule(rule_id: int, data: schema_in, admin: User = Depends(require_roles(ROLE_ADMIN)),
                    db: Session = Depends(get_db)):
        obj = get_owned(db, admin, rule_id)
        for k, v in data.model_dump().items():
            setattr(obj, k, v)
        audit.log(db, admin, f"{label}.updated", prefix.strip("/"), obj.id)
        db.commit()
        db.refresh(obj)
        return obj

    @r.delete("/{rule_id}", status_code=204)
    def delete_rule(rule_id: int, admin: User = Depends(require_roles(ROLE_ADMIN)), db: Session = Depends(get_db)):
        obj = get_owned(db, admin, rule_id)
        db.delete(obj)
        audit.log(db, admin, f"{label}.deleted", prefix.strip("/"), rule_id)
        db.commit()

    return r


routers = [
    make_router("/guidelines", BrandGuideline, S.GuidelineIn, S.GuidelineOut, "guideline"),
    make_router("/facts", ApprovedFact, S.FactIn, S.FactOut, "fact"),
    make_router("/terminology", Terminology, S.TermIn, S.TermOut, "terminology"),
    make_router("/prohibited-words", ProhibitedWord, S.ProhibitedIn, S.ProhibitedOut, "prohibited word"),
    make_router("/claims", ApprovedClaim, S.ClaimIn, S.ClaimOut, "claim"),
]
