import json
import os
import csv
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from io import StringIO
from time import monotonic
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import case, func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .auth import ActorDep, SessionDep, require_visible_employee, visible_employee_ids
from .database import Base, build_engine, build_session_factory, get_session
from .models import (
    Approval,
    AuditEvent,
    Department,
    Employee,
    PendingAction,
    Project,
    ProjectMember,
    TimeEntry,
)
from .schemas import (
    ApprovalDryRunRequest,
    ApprovalOut,
    ConfirmationRequest,
    ConfirmationResponse,
    DepartmentOut,
    DryRunResponse,
    EmployeeOut,
    MonthlyHoursStat,
    ProjectHoursStat,
    ProjectMemberOut,
    ProjectOut,
    SafeAnalyticsQuery,
    SummaryStat,
    TimeEntryBatchDraftRequest,
    TimeEntryDraftRequest,
    TimeEntryOut,
    TimeEntrySuggestionOut,
)
from .seed import seed_demo_data

DEFAULT_DATABASE_URL = "sqlite:///./data/demo.db"
ACTION_TTL_MINUTES = 15
ANALYTICS_TIMEOUT_SECONDS = 1.0
BUSINESS_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "Asia/Shanghai")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _business_today() -> date:
    return datetime.now(ZoneInfo(BUSINESS_TIMEZONE)).date()


def _scoped_entry_query(session: Session, actor: Employee):
    return select(TimeEntry).where(
        TimeEntry.employee_id.in_(visible_employee_ids(session, actor))
    )


def _serialize_preview(payload: dict) -> dict:
    return json.loads(json.dumps(payload, default=str))


def _pending_action(
    session: Session, actor: Employee, action_type: str, payload: dict
) -> PendingAction:
    action = PendingAction(
        token=str(uuid4()),
        actor_id=actor.id,
        action_type=action_type,
        payload=json.dumps(payload, default=str),
        expires_at=_utcnow() + timedelta(minutes=ACTION_TTL_MINUTES),
    )
    session.add(action)
    session.commit()
    return action


def _prepare_time_entry_preview(
    session: Session,
    actor: Employee,
    body: TimeEntryDraftRequest,
) -> tuple[dict, dict]:
    """Validate one proposed entry and return its payload and display preview."""

    employee_id = body.employee_id or actor.id
    if actor.role != "admin" and employee_id != actor.id:
        raise HTTPException(
            status_code=403, detail="Only admins may draft for another employee"
        )
    employee = session.get(Employee, employee_id)
    project = session.get(Project, body.project_id)
    if employee is None or project is None:
        raise HTTPException(status_code=404, detail="Employee or project not found")
    membership = session.scalar(
        select(ProjectMember).where(
            ProjectMember.employee_id == employee_id,
            ProjectMember.project_id == body.project_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=422, detail="Employee is not a member of this project"
        )
    payload = body.model_dump(mode="json")
    payload["employee_id"] = employee_id
    preview = {
        **payload,
        "employee_name": employee.name,
        "project_name": project.name,
        "status": "draft",
    }
    return payload, preview


def _weekly_report_data(
    session: Session, actor: Employee, week_start: date | None
) -> dict:
    """Build one role-scoped weekly report used by JSON and CSV endpoints."""

    today = _business_today()
    start = week_start or (today - timedelta(days=today.weekday()))
    end = start + timedelta(days=6)
    entries = list(
        session.scalars(
            _scoped_entry_query(session, actor)
            .where(TimeEntry.work_date.between(start, end))
            .order_by(TimeEntry.work_date, TimeEntry.id)
        )
    )
    rows = [
        {
            "entry_id": entry.id,
            "employee_id": entry.employee_id,
            "employee_name": entry.employee.name,
            "project_id": entry.project_id,
            "project_name": entry.project.name,
            "work_date": entry.work_date.isoformat(),
            "hours": str(entry.hours),
            "status": entry.status,
            "description": entry.description,
        }
        for entry in entries
    ]
    by_status = {value: Decimal("0") for value in ("draft", "submitted", "approved", "rejected")}
    for entry in entries:
        by_status[entry.status] += entry.hours
    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "total_hours": str(sum((entry.hours for entry in entries), Decimal("0"))),
        "hours_by_status": {key: str(value) for key, value in by_status.items()},
        "entry_count": len(rows),
        "entries": rows,
    }


def create_app(database_url: str | None = None, seed: bool = True) -> FastAPI:
    resolved_url = database_url or os.getenv("DEMO_DATABASE_URL", DEFAULT_DATABASE_URL)
    if resolved_url.startswith("sqlite:///") and ":memory:" not in resolved_url:
        db_path = Path(resolved_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = build_engine(resolved_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Base.metadata.create_all(engine)
        if seed:
            with session_factory() as session:
                seed_demo_data(session, today=_business_today())
        yield
        engine.dispose()

    app = FastAPI(
        title="AcmeWorks Demo Core API",
        version="0.1.0",
        description=(
            "A local-only API backed exclusively by fictional AcmeWorks data. "
            "Use X-Actor-ID to select a seeded demo persona."
        ),
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/me", response_model=EmployeeOut, tags=["identity"])
    def me(actor: ActorDep) -> Employee:
        return actor

    @app.get("/departments", response_model=list[DepartmentOut], tags=["queries"])
    def list_departments(session: SessionDep, actor: ActorDep) -> list[Department]:
        if actor.role == "admin":
            return list(session.scalars(select(Department).order_by(Department.id)))
        department_ids = set(
            session.scalars(
                select(Employee.department_id).where(
                    Employee.id.in_(visible_employee_ids(session, actor))
                )
            )
        )
        return list(
            session.scalars(
                select(Department)
                .where(Department.id.in_(department_ids))
                .order_by(Department.id)
            )
        )

    @app.get("/employees", response_model=list[EmployeeOut], tags=["queries"])
    def list_employees(session: SessionDep, actor: ActorDep) -> list[Employee]:
        return list(
            session.scalars(
                select(Employee)
                .where(Employee.id.in_(visible_employee_ids(session, actor)))
                .order_by(Employee.id)
            )
        )

    @app.get("/employees/{employee_id}", response_model=EmployeeOut, tags=["queries"])
    def get_employee(
        employee_id: int, session: SessionDep, actor: ActorDep
    ) -> Employee:
        employee = session.get(Employee, employee_id)
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found")
        require_visible_employee(session, actor, employee_id)
        return employee

    @app.get("/projects", response_model=list[ProjectOut], tags=["queries"])
    def list_projects(session: SessionDep, actor: ActorDep) -> list[Project]:
        if actor.role == "admin":
            query = select(Project)
        else:
            query = (
                select(Project)
                .join(ProjectMember)
                .where(
                    ProjectMember.employee_id.in_(visible_employee_ids(session, actor))
                )
                .distinct()
            )
        return list(session.scalars(query.order_by(Project.id)))

    @app.get("/projects/{project_id}", response_model=ProjectOut, tags=["queries"])
    def get_project(
        project_id: int, session: SessionDep, actor: ActorDep
    ) -> Project:
        visible_ids = {project.id for project in list_projects(session, actor)}
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if project.id not in visible_ids:
            raise HTTPException(status_code=403, detail="Project is outside actor scope")
        return project

    @app.get(
        "/projects/{project_id}/members",
        response_model=list[ProjectMemberOut],
        tags=["queries"],
    )
    def list_project_members(
        project_id: int, session: SessionDep, actor: ActorDep
    ) -> list[ProjectMember]:
        get_project(project_id, session, actor)
        query = select(ProjectMember).where(ProjectMember.project_id == project_id)
        if actor.role != "admin":
            query = query.where(
                ProjectMember.employee_id.in_(visible_employee_ids(session, actor))
            )
        return list(session.scalars(query.order_by(ProjectMember.id)))

    @app.get("/time-entries", response_model=list[TimeEntryOut], tags=["queries"])
    def list_time_entries(
        session: SessionDep,
        actor: ActorDep,
        employee_id: int | None = None,
        project_id: int | None = None,
        entry_status: str | None = Query(default=None, alias="status"),
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TimeEntry]:
        query = _scoped_entry_query(session, actor)
        if employee_id is not None:
            require_visible_employee(session, actor, employee_id)
            query = query.where(TimeEntry.employee_id == employee_id)
        if project_id is not None:
            query = query.where(TimeEntry.project_id == project_id)
        if entry_status is not None:
            query = query.where(TimeEntry.status == entry_status)
        if start_date is not None:
            query = query.where(TimeEntry.work_date >= start_date)
        if end_date is not None:
            query = query.where(TimeEntry.work_date <= end_date)
        return list(
            session.scalars(query.order_by(TimeEntry.work_date.desc(), TimeEntry.id))
        )

    @app.get(
        "/time-entries/{entry_id}", response_model=TimeEntryOut, tags=["queries"]
    )
    def get_time_entry(
        entry_id: int, session: SessionDep, actor: ActorDep
    ) -> TimeEntry:
        entry = session.get(TimeEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Time entry not found")
        require_visible_employee(session, actor, entry.employee_id)
        return entry

    @app.get("/approvals", response_model=list[ApprovalOut], tags=["queries"])
    def list_approvals(session: SessionDep, actor: ActorDep) -> list[Approval]:
        return list(
            session.scalars(
                select(Approval)
                .join(TimeEntry)
                .where(
                    TimeEntry.employee_id.in_(visible_employee_ids(session, actor))
                )
                .order_by(Approval.created_at.desc(), Approval.id.desc())
            )
        )

    @app.get("/reports/weekly", tags=["reports"])
    def weekly_report(
        session: SessionDep,
        actor: ActorDep,
        week_start: date | None = None,
    ) -> dict:
        return _weekly_report_data(session, actor, week_start)

    @app.get("/reports/weekly.csv", tags=["reports"])
    def weekly_report_csv(
        session: SessionDep,
        actor: ActorDep,
        week_start: date | None = None,
    ) -> Response:
        report = _weekly_report_data(session, actor, week_start)
        output = StringIO()
        fieldnames = [
            "entry_id",
            "employee_id",
            "employee_name",
            "project_id",
            "project_name",
            "work_date",
            "hours",
            "status",
            "description",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report["entries"])
        filename = f"acmeworks-week-{report['week_start']}.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/analytics/query", tags=["analytics"])
    def safe_analytics_query(
        body: SafeAnalyticsQuery,
        session: SessionDep,
        actor: ActorDep,
    ) -> dict:
        """Compile a bounded specification into one parameterized read query."""

        if body.start_date and body.end_date and body.start_date > body.end_date:
            raise HTTPException(422, "start_date must not be after end_date")
        dimensions = {
            "project": Project.name,
            "status": TimeEntry.status,
            "employee": Employee.name,
            "work_date": TimeEntry.work_date,
            "month": func.strftime("%Y-%m", TimeEntry.work_date),
        }
        dimension = dimensions[body.dimension].label("dimension")
        metric = (
            func.coalesce(func.sum(TimeEntry.hours), 0)
            if body.metric == "hours"
            else func.count(TimeEntry.id)
        ).label("value")
        query = (
            select(dimension, metric)
            .select_from(TimeEntry)
            .where(
                TimeEntry.employee_id.in_(visible_employee_ids(session, actor))
            )
        )
        if body.dimension == "project":
            query = query.join(Project, TimeEntry.project_id == Project.id)
        elif body.dimension == "employee":
            query = query.join(Employee, TimeEntry.employee_id == Employee.id)
        if body.start_date:
            query = query.where(TimeEntry.work_date >= body.start_date)
        if body.end_date:
            query = query.where(TimeEntry.work_date <= body.end_date)
        if body.status:
            query = query.where(TimeEntry.status == body.status)
        if body.project_id:
            # Project visibility follows the same scoped entry predicate; an
            # unknown/out-of-scope project therefore yields no rows.
            query = query.where(TimeEntry.project_id == body.project_id)
        if body.employee_id:
            require_visible_employee(session, actor, body.employee_id)
            query = query.where(TimeEntry.employee_id == body.employee_id)
        query = query.group_by(dimension)
        query = query.order_by(metric.desc() if body.order == "desc" else metric.asc())
        query = query.limit(body.limit)

        # SQLite enforces query-only mode on this connection during execution.
        # No caller-provided SQL, table, column, expression, or sort clause is
        # accepted; Pydantic enums select every query component above.
        raw_connection = session.connection().connection.driver_connection
        deadline = monotonic() + ANALYTICS_TIMEOUT_SECONDS
        raw_connection.execute("PRAGMA query_only=ON")
        raw_connection.set_progress_handler(
            lambda: int(monotonic() > deadline), 1000
        )
        try:
            try:
                rows = session.execute(query).all()
            except OperationalError as exc:
                if "interrupted" in str(exc).casefold():
                    raise HTTPException(
                        408, "Analytics query exceeded its execution budget"
                    ) from exc
                raise
        finally:
            raw_connection.set_progress_handler(None, 0)
            raw_connection.execute("PRAGMA query_only=OFF")
        return {
            "dimension": body.dimension,
            "metric": body.metric,
            "row_count": len(rows),
            "rows": [
                {"dimension": str(row.dimension), "value": str(row.value)}
                for row in rows
            ],
        }

    @app.get(
        "/stats/hours-by-project",
        response_model=list[ProjectHoursStat],
        tags=["statistics"],
    )
    def hours_by_project(
        session: SessionDep,
        actor: ActorDep,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        query = (
            select(
                Project.id,
                Project.name,
                func.coalesce(func.sum(TimeEntry.hours), 0),
            )
            .join(TimeEntry)
            .where(TimeEntry.employee_id.in_(visible_employee_ids(session, actor)))
            .group_by(Project.id, Project.name)
            .order_by(Project.id)
        )
        if start_date:
            query = query.where(TimeEntry.work_date >= start_date)
        if end_date:
            query = query.where(TimeEntry.work_date <= end_date)
        return [
            {"project_id": row[0], "project_name": row[1], "hours": row[2]}
            for row in session.execute(query)
        ]

    @app.get(
        "/stats/monthly-hours",
        response_model=list[MonthlyHoursStat],
        tags=["statistics"],
    )
    def monthly_hours(session: SessionDep, actor: ActorDep) -> list[dict]:
        month = func.strftime("%Y-%m", TimeEntry.work_date)
        rows = session.execute(
            select(month, func.sum(TimeEntry.hours))
            .where(TimeEntry.employee_id.in_(visible_employee_ids(session, actor)))
            .group_by(month)
            .order_by(month)
        )
        return [{"month": row[0], "hours": row[1]} for row in rows]

    @app.get("/stats/summary", response_model=SummaryStat, tags=["statistics"])
    def summary(session: SessionDep, actor: ActorDep) -> dict:
        columns = [func.coalesce(func.sum(TimeEntry.hours), 0)]
        for value in ("draft", "submitted", "approved", "rejected"):
            columns.append(
                func.coalesce(
                    func.sum(case((TimeEntry.status == value, TimeEntry.hours), else_=0)),
                    0,
                )
            )
        row = session.execute(
            select(*columns).where(
                TimeEntry.employee_id.in_(visible_employee_ids(session, actor))
            )
        ).one()
        return dict(
            zip(
                (
                    "total_hours",
                    "draft_hours",
                    "submitted_hours",
                    "approved_hours",
                    "rejected_hours",
                ),
                row,
                strict=True,
            )
        )

    @app.get(
        "/time-entry-suggestions",
        response_model=list[TimeEntrySuggestionOut],
        tags=["queries"],
    )
    def time_entry_suggestions(
        session: SessionDep,
        actor: ActorDep,
        target_date: date | None = None,
    ) -> list[dict]:
        """Suggest recent personal work without creating a pending action."""

        suggestion_date = target_date or _business_today()
        memberships = set(
            session.scalars(
                select(ProjectMember.project_id).where(
                    ProjectMember.employee_id == actor.id
                )
            )
        )
        recent_entries = session.scalars(
            select(TimeEntry)
            .where(
                TimeEntry.employee_id == actor.id,
                TimeEntry.project_id.in_(memberships),
            )
            .order_by(TimeEntry.work_date.desc(), TimeEntry.id.desc())
        )
        suggestions: list[dict] = []
        seen_projects: set[int] = set()
        for entry in recent_entries:
            if entry.project_id in seen_projects or entry.project.status != "active":
                continue
            seen_projects.add(entry.project_id)
            suggestions.append(
                {
                    "project_id": entry.project_id,
                    "project_name": entry.project.name,
                    "target_date": suggestion_date,
                    "suggested_hours": entry.hours,
                    "suggested_description": entry.description,
                    "based_on_entry_id": entry.id,
                    "based_on_date": entry.work_date,
                }
            )
            if len(suggestions) == 3:
                break
        return suggestions

    @app.post(
        "/time-entries/dry-run",
        response_model=DryRunResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["writes"],
    )
    def dry_run_time_entry(
        body: TimeEntryDraftRequest, session: SessionDep, actor: ActorDep
    ) -> DryRunResponse:
        payload, preview = _prepare_time_entry_preview(session, actor, body)
        action = _pending_action(session, actor, "create_time_entry", payload)
        return DryRunResponse(
            action="create_time_entry",
            preview=_serialize_preview(preview),
            confirmation_token=action.token,
            expires_at=action.expires_at,
        )

    @app.post(
        "/time-entries/batch/dry-run",
        response_model=DryRunResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["writes"],
    )
    def dry_run_time_entry_batch(
        body: TimeEntryBatchDraftRequest,
        session: SessionDep,
        actor: ActorDep,
    ) -> DryRunResponse:
        """Validate an entire batch before issuing one confirmation token."""

        prepared = [
            _prepare_time_entry_preview(session, actor, entry)
            for entry in body.entries
        ]
        payload = {"entries": [item[0] for item in prepared]}
        preview = {
            "count": len(prepared),
            "entries": [item[1] for item in prepared],
        }
        action = _pending_action(session, actor, "create_time_entries", payload)
        return DryRunResponse(
            action="create_time_entries",
            preview=_serialize_preview(preview),
            confirmation_token=action.token,
            expires_at=action.expires_at,
        )

    @app.post(
        "/time-entries/{entry_id}/approval/dry-run",
        response_model=DryRunResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["writes"],
    )
    def dry_run_approval(
        entry_id: int,
        body: ApprovalDryRunRequest,
        session: SessionDep,
        actor: ActorDep,
    ) -> DryRunResponse:
        entry = session.get(TimeEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Time entry not found")
        if actor.role not in {"manager", "admin"}:
            raise HTTPException(status_code=403, detail="Approval role required")
        if actor.role == "manager" and entry.employee.manager_id != actor.id:
            raise HTTPException(
                status_code=403, detail="Managers may approve direct reports only"
            )
        if entry.employee_id == actor.id:
            raise HTTPException(status_code=403, detail="Self-approval is not allowed")
        if entry.status != "submitted":
            raise HTTPException(
                status_code=409, detail="Only submitted entries can be decided"
            )
        payload = {
            "entry_id": entry.id,
            "decision": body.decision,
            "comment": body.comment,
        }
        action = _pending_action(session, actor, "decide_time_entry", payload)
        preview = {
            **payload,
            "employee_name": entry.employee.name,
            "project_name": entry.project.name,
            "work_date": entry.work_date,
            "hours": entry.hours,
        }
        return DryRunResponse(
            action="decide_time_entry",
            preview=_serialize_preview(preview),
            confirmation_token=action.token,
            expires_at=action.expires_at,
        )

    @app.post(
        "/actions/{confirmation_token}/confirm",
        response_model=ConfirmationResponse,
        tags=["writes"],
    )
    def confirm_action(
        confirmation_token: str,
        _: ConfirmationRequest,
        session: SessionDep,
        actor: ActorDep,
    ) -> ConfirmationResponse:
        action = session.get(PendingAction, confirmation_token)
        if action is None:
            raise HTTPException(status_code=404, detail="Confirmation token not found")
        if action.actor_id != actor.id:
            raise HTTPException(
                status_code=403, detail="Confirmation token belongs to another actor"
            )
        if action.consumed_at is not None:
            raise HTTPException(
                status_code=409, detail="Confirmation token has already been used"
            )
        if action.expires_at < _utcnow():
            raise HTTPException(status_code=410, detail="Confirmation token has expired")

        consumed = session.execute(
            update(PendingAction)
            .where(
                PendingAction.token == confirmation_token,
                PendingAction.actor_id == actor.id,
                PendingAction.consumed_at.is_(None),
            )
            .values(consumed_at=_utcnow())
        )
        if consumed.rowcount != 1:
            session.rollback()
            raise HTTPException(
                status_code=409, detail="Confirmation token has already been used"
            )

        payload = json.loads(action.payload)
        if action.action_type == "create_time_entry":
            employee = session.get(Employee, payload["employee_id"])
            project = session.get(Project, payload["project_id"])
            if employee is None or project is None:
                raise HTTPException(
                    status_code=409,
                    detail="Employee or project no longer exists",
                )
            if actor.role != "admin" and employee.id != actor.id:
                raise HTTPException(
                    status_code=403,
                    detail="Actor is no longer authorized to create this draft",
                )
            membership = session.scalar(
                select(ProjectMember).where(
                    ProjectMember.employee_id == employee.id,
                    ProjectMember.project_id == project.id,
                )
            )
            if membership is None:
                raise HTTPException(
                    status_code=409,
                    detail="Employee is no longer a member of this project",
                )
            entry = TimeEntry(
                employee_id=employee.id,
                project_id=project.id,
                work_date=date.fromisoformat(payload["work_date"]),
                hours=Decimal(payload["hours"]),
                description=payload["description"],
                status="draft",
            )
            session.add(entry)
            session.flush()
            result = TimeEntryOut.model_validate(entry).model_dump(mode="json")
            resource_id = str(entry.id)
        elif action.action_type == "create_time_entries":
            created_entries: list[TimeEntry] = []
            for item in payload["entries"]:
                employee = session.get(Employee, item["employee_id"])
                project = session.get(Project, item["project_id"])
                if employee is None or project is None:
                    raise HTTPException(
                        status_code=409,
                        detail="A batch employee or project no longer exists",
                    )
                if actor.role != "admin" and employee.id != actor.id:
                    raise HTTPException(
                        status_code=403,
                        detail="Actor is no longer authorized for this batch",
                    )
                membership = session.scalar(
                    select(ProjectMember).where(
                        ProjectMember.employee_id == employee.id,
                        ProjectMember.project_id == project.id,
                    )
                )
                if membership is None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "An employee is no longer a member of a batch project"
                        ),
                    )
                created_entries.append(
                    TimeEntry(
                        employee_id=employee.id,
                        project_id=project.id,
                        work_date=date.fromisoformat(item["work_date"]),
                        hours=Decimal(item["hours"]),
                        description=item["description"],
                        status="draft",
                    )
                )
            session.add_all(created_entries)
            session.flush()
            result = {
                "count": len(created_entries),
                "time_entries": [
                    TimeEntryOut.model_validate(entry).model_dump(mode="json")
                    for entry in created_entries
                ],
            }
            resource_id = f"batch:{len(created_entries)}"
        elif action.action_type == "decide_time_entry":
            entry = session.get(TimeEntry, payload["entry_id"])
            if entry is None:
                raise HTTPException(status_code=404, detail="Time entry not found")
            if actor.role not in {"manager", "admin"}:
                raise HTTPException(
                    status_code=403, detail="Actor no longer has an approval role"
                )
            if actor.role == "manager" and entry.employee.manager_id != actor.id:
                raise HTTPException(
                    status_code=403,
                    detail="Entry is no longer in the manager's direct team",
                )
            if entry.employee_id == actor.id:
                raise HTTPException(
                    status_code=403, detail="Self-approval is not allowed"
                )
            if entry.status != "submitted":
                raise HTTPException(
                    status_code=409, detail="Time entry is no longer submitted"
                )
            entry.status = payload["decision"]
            approval = Approval(
                time_entry_id=entry.id,
                actor_id=actor.id,
                decision=payload["decision"],
                comment=payload.get("comment"),
            )
            session.add(approval)
            session.flush()
            result = {
                "time_entry": TimeEntryOut.model_validate(entry).model_dump(mode="json"),
                "approval": ApprovalOut.model_validate(approval).model_dump(mode="json"),
            }
            resource_id = str(entry.id)
        else:
            raise HTTPException(status_code=409, detail="Unsupported pending action")

        session.add(
            AuditEvent(
                actor_id=actor.id,
                action=action.action_type,
                resource_type="time_entry",
                resource_id=resource_id,
                details=json.dumps(payload),
            )
        )
        session.commit()
        return ConfirmationResponse(
            action=action.action_type, result=_serialize_preview(result)
        )

    return app


app = create_app()
