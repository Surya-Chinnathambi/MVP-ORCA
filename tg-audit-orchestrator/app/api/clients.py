from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_permission
from app.models.clients import Client
from app.models.users import User
from app.schemas.clients import ClientCreate, ClientOut, ClientUpdate

# Roles allowed to create / mutate clients per RBAC.md §3
_CLIENT_WRITE_ROLES = ("platform_admin", "partner", "pm")

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=List[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.query(Client).all()


@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(*_CLIENT_WRITE_ROLES)),
):
    client = Client(**body.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: str,
    body: ClientUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(*_CLIENT_WRITE_ROLES)),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(client, field, val)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("platform_admin", "partner")),
):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
