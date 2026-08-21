from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)

    employees: Mapped[list["Employee"]] = relationship(back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))

    department: Mapped[Department] = relationship(back_populates="employees")
    manager: Mapped["Employee | None"] = relationship(
        remote_side=[id], back_populates="direct_reports"
    )
    direct_reports: Mapped[list["Employee"]] = relationship(back_populates="manager")
    project_memberships: Mapped[list["ProjectMember"]] = relationship(
        back_populates="employee"
    )
    time_entries: Mapped[list["TimeEntry"]] = relationship(back_populates="employee")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))

    department: Mapped[Department] = relationship()
    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project")
    time_entries: Mapped[list["TimeEntry"]] = relationship(back_populates="project")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "employee_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    project_role: Mapped[str] = mapped_column(String(100))

    project: Mapped[Project] = relationship(back_populates="members")
    employee: Mapped[Employee] = relationship(back_populates="project_memberships")


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    work_date: Mapped[date] = mapped_column(Date)
    hours: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    description: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    employee: Mapped[Employee] = relationship(back_populates="time_entries")
    project: Mapped[Project] = relationship(back_populates="time_entries")
    approvals: Mapped[list["Approval"]] = relationship(back_populates="time_entry")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    time_entry_id: Mapped[int] = mapped_column(ForeignKey("time_entries.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    time_entry: Mapped[TimeEntry] = relationship(back_populates="approvals")
    actor: Mapped[Employee] = relationship()


class PendingAction(Base):
    __tablename__ = "pending_actions"

    token: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    action_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IntegrationSource(Base):
    __tablename__ = "integration_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_id: Mapped[str] = mapped_column(String(80), unique=True)
    source_account_ref_hash: Mapped[str] = mapped_column(String(64))
    calendar_id_hash: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mode: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IntegrationPersonMapping(Base):
    __tablename__ = "integration_person_mappings"
    __table_args__ = (UniqueConstraint("integration_id", "person_ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_id: Mapped[str] = mapped_column(String(80))
    person_ref: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))


class IntegrationProjectMapping(Base):
    __tablename__ = "integration_project_mappings"
    __table_args__ = (UniqueConstraint("integration_id", "project_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_id: Mapped[str] = mapped_column(String(80))
    project_code: Mapped[str] = mapped_column(String(32))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))


class IntegrationNonce(Base):
    __tablename__ = "integration_nonces"
    __table_args__ = (UniqueConstraint("integration_id", "nonce_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_id: Mapped[str] = mapped_column(String(80))
    nonce_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IntegrationSuggestion(Base):
    __tablename__ = "integration_suggestions"
    __table_args__ = (UniqueConstraint("integration_id", "source_event_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    integration_id: Mapped[str] = mapped_column(String(80))
    source_event_key: Mapped[str] = mapped_column(String(64))
    current_revision_key: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    person_ref: Mapped[str] = mapped_column(String(64))
    project_code: Mapped[str] = mapped_column(String(32))
    work_date: Mapped[date] = mapped_column(Date)
    duration_minutes: Mapped[int]
    description: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(24), default="suggested")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IntegrationSuggestionRevision(Base):
    __tablename__ = "integration_suggestion_revisions"
    __table_args__ = (UniqueConstraint("integration_id", "revision_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_id: Mapped[str] = mapped_column(String(80))
    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("integration_suggestions.id")
    )
    revision_key: Mapped[str] = mapped_column(String(64))
    event_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TimeEntrySourceLink(Base):
    __tablename__ = "time_entry_source_links"
    __table_args__ = (UniqueConstraint("integration_id", "source_event_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    integration_id: Mapped[str] = mapped_column(String(80))
    source_event_key: Mapped[str] = mapped_column(String(64))
    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("integration_suggestions.id"), unique=True
    )
    time_entry_id: Mapped[int] = mapped_column(
        ForeignKey("time_entries.id"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IntegrationOutbox(Base):
    __tablename__ = "integration_outbox"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    suggestion_id: Mapped[str] = mapped_column(
        ForeignKey("integration_suggestions.id"), unique=True
    )
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    attempt_count: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("event_id", "attempt_no"),)

    delivery_attempt_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("integration_outbox.event_id"))
    attempt_no: Mapped[int]
    channel_ref_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    claim_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
