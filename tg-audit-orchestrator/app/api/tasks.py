"""Task board — status transitions with approval gating for cancellation."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models.clients import Project
from app.models.tasks import Task
from app.models.users import User
from app.schemas.approvals import ApprovalOut
from app.schemas.tasks import VALID_STATUSES, TaskCreate, TaskOut, TaskUpdate
from app.services.audit import request_approval

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])

_GATED_TRANSITIONS = {"cancelled"}   # transitions that require approval


def _project_or_404(project_id: str, db: Session) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return p


@router.get("/", response_model=List[TaskOut])
def list_tasks(
    project_id: str,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    q = db.query(Task).filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    if kind:
        q = q.filter_by(kind=kind)
    return q.all()


@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: str,
    body: TaskCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    task = Task(
        project_id=project_id,
        kind=body.kind,
        title=body.title,
        status="open",
        assignee_id=body.assignee_id,
        due_date=body.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    project_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _project_or_404(project_id, db)
    task = db.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}")
def update_task(
    project_id: str,
    task_id: str,
    body: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update task fields. Transitioning to 'cancelled' requires approval —
    returns ApprovalOut instead of TaskOut in that case."""
    _project_or_404(project_id, db)
    task = db.get(Task, task_id)
    if task is None or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")

    new_status = body.status
    if new_status and new_status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status '{new_status}'")

    # Gated transition: cancellation requires approval
    if new_status in _GATED_TRANSITIONS:
        approval = request_approval(
            db,
            project_id=project_id,
            target_type="task_cancellation",
            target_id=task_id,
            reason=f"Cancel task: {task.title}",
            approver_role="pm",
            change_before={"status": task.status},
            change_after={"status": "cancelled"},
            requested_by=current_user.id,
        )
        db.commit()
        db.refresh(approval)
        return approval   # caller receives ApprovalOut

    # Non-gated updates apply immediately
    updates = body.model_dump(exclude_unset=True)
    for field, val in updates.items():
        setattr(task, field, val)
    db.commit()
    db.refresh(task)
    return task
