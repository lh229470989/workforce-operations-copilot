from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.config import Settings
from app.main import create_app
from app.planner import LocalPlanner


class FakeCoreClient:
    def __init__(self):
        self.dry_run_calls = []
        self.batch_dry_run_calls = []
        self.approval_dry_run_calls = []
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
        if actor_id not in {1, 2, 3}:
            raise HTTPException(status_code=401, detail="Unknown actor")
        role = "admin" if actor_id == 1 else "manager" if actor_id == 2 else "employee"
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

    async def get_weekly_report(self, actor_id, week_start=None):
        start = week_start.isoformat() if week_start else "2026-07-20"
        return {
            "week_start": start,
            "week_end": "2026-07-26",
            "total_hours": "13.50",
            "hours_by_status": {
                "draft": "0.00",
                "submitted": "6.00",
                "approved": "7.50",
                "rejected": "0.00",
            },
            "entry_count": 2,
            "entries": self.entries,
        }

    async def run_safe_analytics(self, actor_id, payload):
        groups = {
            "project": [("Apollo", "13.50")],
            "status": [("approved", "7.50"), ("submitted", "6.00")],
            "employee": [("Jamie Rivera", "13.50")],
            "work_date": [("2026-07-20", "7.50"), ("2026-07-21", "6.00")],
            "month": [("2026-07", "13.50")],
        }
        rows = [
            {"dimension": dimension, "value": value}
            for dimension, value in groups[payload["dimension"]]
        ]
        return {
            "dimension": payload["dimension"],
            "metric": payload["metric"],
            "row_count": len(rows),
            "rows": rows,
        }

    async def get_time_entry_suggestions(self, actor_id, target_date=None):
        return [
            {
                "project_id": 1,
                "project_name": "Apollo",
                "target_date": (
                    target_date.isoformat()
                    if target_date is not None
                    else "2026-07-22"
                ),
                "suggested_hours": "6.00",
                "suggested_description": "Validated exports",
                "based_on_entry_id": 2,
                "based_on_date": "2026-07-21",
            }
        ]

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
            "expires_at": "2026-07-22T12:15:00Z",
        }

    async def dry_run_time_entry_batch(self, actor_id, payload):
        self.batch_dry_run_calls.append((actor_id, payload))
        preview_entries = [
            {
                **entry,
                "employee_id": actor_id,
                "employee_name": "Jamie Rivera",
                "project_name": "Apollo",
                "status": "draft",
            }
            for entry in payload["entries"]
        ]
        return {
            "dry_run": True,
            "action": "create_time_entries",
            "preview": {
                "count": len(preview_entries),
                "entries": preview_entries,
            },
            "confirmation_token": "batch-demo-token",
            "expires_at": "2026-07-22T12:15:00Z",
        }

    async def dry_run_approval(self, actor_id, time_entry_id, payload):
        self.approval_dry_run_calls.append(
            (actor_id, time_entry_id, payload)
        )
        return {
            "dry_run": True,
            "action": "decide_time_entry",
            "preview": {
                "entry_id": time_entry_id,
                "decision": payload["decision"],
                "comment": payload.get("comment"),
                "employee_name": "Jamie Rivera",
                "project_name": "Apollo",
                "work_date": "2026-07-21",
                "hours": "6.00",
            },
            "confirmation_token": "approval-demo-token",
            "expires_at": "2026-07-22T12:15:00Z",
        }

    async def dry_run_approval_batch(self, actor_id, payload):
        return {
            "dry_run": True,
            "action": "decide_time_entries",
            "preview": {"count": len(payload["entry_ids"]), **payload},
            "confirmation_token": "approval-batch-token",
            "expires_at": "2026-07-22T12:15:00Z",
        }

    async def dry_run_time_entry_lifecycle(
        self, actor_id, time_entry_id, action, payload=None
    ):
        return {
            "dry_run": True,
            "action": {
                "update": "update_time_entry",
                "delete": "delete_time_entry",
                "submit": "transition_time_entry",
                "withdraw": "transition_time_entry",
            }[action],
            "preview": {"entry_id": time_entry_id, "action": action, "changes": payload},
            "confirmation_token": "lifecycle-token",
            "expires_at": "2026-07-22T12:15:00Z",
        }


@pytest.fixture
def fake_core():
    return FakeCoreClient()


@pytest.fixture
def client(fake_core, tmp_path):
    # Tests must name their authored policy fixture explicitly. Relying on the
    # process working directory hides packaging and CI path regressions.
    knowledge_base_path = Path(__file__).resolve().parents[3] / "knowledge-base"
    assert (knowledge_base_path / "time-reporting.md").is_file()
    settings = Settings(
        core_api_base_url="http://core.test",
        ai_mode="local",
        knowledge_base_path=str(knowledge_base_path),
        state_database_path=str(tmp_path / "ai-state.db"),
    )
    app = create_app(
        settings,
        core_client=fake_core,
        planner=LocalPlanner(),
        today_provider=lambda: date(2026, 7, 22),
    )
    with TestClient(app) as test_client:
        yield test_client
