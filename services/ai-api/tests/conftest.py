from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.planner import LocalPlanner


class FakeCoreClient:
    def __init__(self):
        self.dry_run_calls = []
        self.projects = [
            {
                "id": 1,
                "name": "Apollo",
                "code": "APL",
                "description": "Synthetic analytics",
                "status": "active",
                "department_id": 1,
            },
            {
                "id": 2,
                "name": "Beacon",
                "code": "BCN",
                "description": "Synthetic planning",
                "status": "active",
                "department_id": 1,
            },
        ]
        self.departments = [
            {"id": 1, "name": "Product Engineering", "code": "ENG"}
        ]
        self.employees = [
            {
                "id": 2,
                "name": "Morgan Lee",
                "email": "morgan.lee@acmeworks.example",
                "role": "manager",
                "title": "Engineering Manager",
                "department_id": 1,
                "manager_id": 1,
            },
            {
                "id": 3,
                "name": "Jamie Rivera",
                "email": "jamie.rivera@acmeworks.example",
                "role": "employee",
                "title": "Software Engineer",
                "department_id": 1,
                "manager_id": 2,
            },
        ]
        self.members = [
            {
                "id": 1,
                "project_id": 1,
                "employee_id": 3,
                "project_role": "Engineer",
            }
        ]
        self.entries = [
            {
                "id": 1,
                "employee_id": 3,
                "project_id": 1,
                "work_date": "2026-07-20",
                "hours": "7.50",
                "description": "Built filters",
                "status": "approved",
                "created_at": "2026-07-20T10:00:00",
                "updated_at": "2026-07-20T10:00:00",
            },
            {
                "id": 2,
                "employee_id": 3,
                "project_id": 1,
                "work_date": "2026-07-21",
                "hours": "6.00",
                "description": "Validated exports",
                "status": "submitted",
                "created_at": "2026-07-21T10:00:00",
                "updated_at": "2026-07-21T10:00:00",
            },
        ]

    async def close(self):
        return None

    async def health(self):
        return {"status": "ok"}

    async def get_me(self, actor_id):
        role = "manager" if actor_id == 2 else "employee"
        return {
            "id": actor_id,
            "name": "Morgan Lee" if actor_id == 2 else "Jamie Rivera",
            "role": role,
            "title": (
                "Engineering Manager"
                if actor_id == 2
                else "Software Engineer"
            ),
        }

    async def list_departments(self, actor_id):
        return self.departments

    async def list_employees(self, actor_id):
        if actor_id == 3:
            return [employee for employee in self.employees if employee["id"] == 3]
        return self.employees

    async def list_projects(self, actor_id):
        return self.projects

    async def list_project_members(self, actor_id, project_id):
        return [
            member
            for member in self.members
            if member["project_id"] == project_id
        ]

    async def list_time_entries(self, actor_id, **filters):
        result = self.entries
        if filters.get("project_id"):
            result = [
                entry
                for entry in result
                if entry["project_id"] == filters["project_id"]
            ]
        if filters.get("start_date"):
            start = filters["start_date"].isoformat()
            result = [entry for entry in result if entry["work_date"] >= start]
        if filters.get("end_date"):
            end = filters["end_date"].isoformat()
            result = [entry for entry in result if entry["work_date"] <= end]
        if filters.get("status"):
            result = [
                entry for entry in result if entry["status"] == filters["status"]
            ]
        return result

    async def get_summary(self, actor_id):
        return {
            "total_hours": "13.50",
            "draft_hours": "0.00",
            "submitted_hours": "6.00",
            "approved_hours": "7.50",
            "rejected_hours": "0.00",
        }

    async def dry_run_time_entry(self, actor_id, payload):
        self.dry_run_calls.append((actor_id, payload))
        return {
            "dry_run": True,
            "action": "create_time_entry",
            "preview": {
                **payload,
                "employee_id": actor_id,
                "employee_name": "Jamie Rivera",
                "project_name": "Apollo",
                "status": "draft",
            },
            "confirmation_token": "demo-token",
            "expires_at": "2026-07-22T12:15:00",
        }


@pytest.fixture
def fake_core():
    return FakeCoreClient()


@pytest.fixture
def client(fake_core):
    settings = Settings(
        core_api_base_url="http://core.test",
        ai_mode="local",
    )
    app = create_app(
        settings,
        core_client=fake_core,
        planner=LocalPlanner(),
        today_provider=lambda: date(2026, 7, 22),
    )
    with TestClient(app) as test_client:
        yield test_client
