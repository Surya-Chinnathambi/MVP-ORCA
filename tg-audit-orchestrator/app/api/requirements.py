"""Requirements tracker — list and filter requirements per project."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.scope import Requirement
from app.models.users import User
from app.schemas.requirements import RequirementOut

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


def _project_or_404(project_id: str, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.get("/", response_model=List[RequirementOut])
def list_requirements(
    project_id: str,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List requirements for a project, optionally filtered by category."""
    _project_or_404(project_id, db)
    q = db.query(Requirement).filter_by(project_id=project_id)
    if category:
        q = q.filter_by(category=category)
    return q.order_by(Requirement.ref_code).all()


@router.get("/{req_id}", response_model=RequirementOut)
def get_requirement(
    project_id: str,
    req_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    req = db.get(Requirement, req_id)
    if req is None or req.project_id != project_id:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return req


@router.get("/categories/list")
def list_categories(
    project_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> List[str]:
    """Return the distinct requirement categories for a project."""
    _project_or_404(project_id, db)
    rows = (
        db.query(Requirement.category)
        .filter_by(project_id=project_id)
        .distinct()
        .all()
    )
    return sorted(r[0] for r in rows)
