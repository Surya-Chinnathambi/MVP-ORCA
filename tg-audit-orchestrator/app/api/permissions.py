from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models.users import Permission, Role, User
from app.schemas.permissions import PermissionCreate, PermissionOut

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.get("/", response_model=List[PermissionOut], dependencies=[Depends(require_admin)])
def list_permissions(user_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Permission)
    if user_id:
        q = q.filter_by(user_id=user_id)
    return q.all()


@router.post("/", response_model=PermissionOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_admin)])
def create_permission(body: PermissionCreate, db: Session = Depends(get_db)):
    if db.get(User, body.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if db.get(Role, body.role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    perm = Permission(
        user_id=body.user_id,
        role_id=body.role_id,
        scope_level=body.scope_level,
        scope_id=body.scope_id,
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    return perm


@router.delete("/{perm_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
def delete_permission(perm_id: str, db: Session = Depends(get_db)):
    perm = db.get(Permission, perm_id)
    if perm is None:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
