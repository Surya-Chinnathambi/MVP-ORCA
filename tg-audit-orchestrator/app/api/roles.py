from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models.users import Role
from app.schemas.roles import RoleOut

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("/", response_model=List[RoleOut], dependencies=[Depends(require_admin)])
def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).all()
