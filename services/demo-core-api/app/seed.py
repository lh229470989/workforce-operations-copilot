from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Approval, Department, Employee, Project, ProjectMember, TimeEntry


def seed_demo_data(session: Session, today: date | None = None) -> bool:
    if session.scalar(select(func.count()).select_from(Employee)):
        return False
    reference_date = today or date.today()
    week_start = reference_date - timedelta(days=reference_date.weekday())
    previous_month_end = week_start.replace(day=1) - timedelta(days=1)

    departments = [
        Department(id=1, name="Product Engineering", code="ENG"),
        Department(id=2, name="Customer Success", code="CS"),
        Department(id=3, name="People Operations", code="PEOPLE"),
    ]
    employees = [
        Employee(
            id=1,
            name="Avery Chen",
            email="avery.chen@acmeworks.example",
            role="admin",
            title="People Systems Administrator",
            department_id=3,
        ),
        Employee(
            id=2,
            name="Morgan Lee",
            email="morgan.lee@acmeworks.example",
            role="manager",
            title="Engineering Manager",
            department_id=1,
        ),
        Employee(
            id=3,
            name="Jamie Rivera",
            email="jamie.rivera@acmeworks.example",
            role="employee",
            title="Software Engineer",
            department_id=1,
            manager_id=2,
        ),
        Employee(
            id=4,
            name="Priya Nair",
            email="priya.nair@acmeworks.example",
            role="employee",
            title="Product Designer",
            department_id=1,
            manager_id=2,
        ),
        Employee(
            id=5,
            name="Taylor Brooks",
            email="taylor.brooks@acmeworks.example",
            role="manager",
            title="Customer Success Manager",
            department_id=2,
        ),
        Employee(
            id=6,
            name="Noah Williams",
            email="noah.williams@acmeworks.example",
            role="employee",
            title="Customer Success Specialist",
            department_id=2,
            manager_id=5,
        ),
    ]
    projects = [
        Project(
            id=1,
            name="Apollo",
            code="APL",
            description="A fictional self-service analytics workspace.",
            status="active",
            department_id=1,
        ),
        Project(
            id=2,
            name="Beacon",
            code="BCN",
            description="A fictional customer onboarding improvement program.",
            status="active",
            department_id=2,
        ),
        Project(
            id=3,
            name="Cedar",
            code="CDR",
            description="A fictional internal learning initiative.",
            status="planned",
            department_id=3,
        ),
    ]
    members = [
        ProjectMember(id=1, project_id=1, employee_id=2, project_role="Lead"),
        ProjectMember(id=2, project_id=1, employee_id=3, project_role="Engineer"),
        ProjectMember(id=3, project_id=1, employee_id=4, project_role="Designer"),
        ProjectMember(id=4, project_id=2, employee_id=5, project_role="Lead"),
        ProjectMember(id=5, project_id=2, employee_id=6, project_role="Specialist"),
        ProjectMember(id=6, project_id=3, employee_id=1, project_role="Sponsor"),
    ]
    entries = [
        TimeEntry(
            id=1,
            employee_id=3,
            project_id=1,
            work_date=week_start,
            hours=Decimal("7.50"),
            description="Implemented dashboard filters",
            status="approved",
        ),
        TimeEntry(
            id=2,
            employee_id=3,
            project_id=1,
            work_date=week_start + timedelta(days=1),
            hours=Decimal("6.00"),
            description="Added export validation",
            status="submitted",
        ),
        TimeEntry(
            id=3,
            employee_id=4,
            project_id=1,
            work_date=week_start + timedelta(days=1),
            hours=Decimal("5.50"),
            description="Refined analytics workspace prototype",
            status="submitted",
        ),
        TimeEntry(
            id=4,
            employee_id=6,
            project_id=2,
            work_date=week_start + timedelta(days=2),
            hours=Decimal("8.00"),
            description="Prepared onboarding workshop",
            status="approved",
        ),
        TimeEntry(
            id=5,
            employee_id=2,
            project_id=1,
            work_date=previous_month_end,
            hours=Decimal("3.00"),
            description="Planned the July delivery cycle",
            status="approved",
        ),
    ]
    approvals = [
        Approval(
            id=1,
            time_entry_id=1,
            actor_id=2,
            decision="approved",
            comment="Clear delivery notes",
        ),
        Approval(
            id=2,
            time_entry_id=4,
            actor_id=5,
            decision="approved",
            comment="Workshop preparation confirmed",
        ),
        Approval(
            id=3,
            time_entry_id=5,
            actor_id=1,
            decision="approved",
            comment="Planning entry reviewed",
        ),
    ]
    session.add_all(
        departments + employees + projects + members + entries + approvals
    )
    session.commit()
    return True
