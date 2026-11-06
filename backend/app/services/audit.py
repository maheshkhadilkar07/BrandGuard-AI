from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log(db: Session, user: Optional[User], action: str, entity_type: Optional[str] = None,
        entity_id: Optional[int] = None, details: Optional[str] = None, organisation_id: Optional[int] = None):
    """Add an audit record to the session. The caller commits."""
    db.add(AuditLog(
        organisation_id=organisation_id if organisation_id is not None else (user.organisation_id if user else None),
        user_id=user.id if user else None, action=action, entity_type=entity_type,
        entity_id=entity_id, details=(details or "")[:1000] or None))
