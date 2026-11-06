from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ROLE_ADMIN
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models import Organisation, User
from app.schemas.auth import OrganisationIn, OrganisationOut
from app.services import audit

router = APIRouter(tags=["Organisation"])


@router.get("/organisations/public")
def public_organisations(db: Session = Depends(get_db)):
    """Names only, so new creators can choose their organisation when registering."""
    return [{"id": o.id, "name": o.name} for o in db.scalars(select(Organisation).order_by(Organisation.name))]


@router.get("/organisation", response_model=OrganisationOut)
def get_organisation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.get(Organisation, user.organisation_id)


@router.put("/organisation", response_model=OrganisationOut)
def update_organisation(data: OrganisationIn, user: User = Depends(require_roles(ROLE_ADMIN)),
                        db: Session = Depends(get_db)):
    org = db.get(Organisation, user.organisation_id)
    for k, v in data.model_dump().items():
        setattr(org, k, v)
    audit.log(db, user, "organisation.updated", "organisation", org.id)
    db.commit()
    db.refresh(org)
    return org
