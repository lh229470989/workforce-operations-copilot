from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_session
from .models import Employee

SessionDep = Annotated[Session, Depends(get_session)]


def get_actor(
    session: SessionDep,
    actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
) -> Employee:
    if actor_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Actor-ID header is required",
        )
    actor = session.get(Employee, actor_id)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown actor"
        )
    return actor


ActorDep = Annotated[Employee, Depends(get_actor)]


def visible_employee_ids(session: Session, actor: Employee) -> set[int]:
    if actor.role == "admin":
        return set(session.scalars(select(Employee.id)))
    if actor.role == "manager":
        report_ids = set(
            session.scalars(select(Employee.id).where(Employee.manager_id == actor.id))
        )
        return report_ids | {actor.id}
    return {actor.id}


def require_visible_employee(
    session: Session, actor: Employee, employee_id: int
) -> None:
    if employee_id not in visible_employee_ids(session, actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee is outside the actor's authorized scope",
        )
