def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_identity_requires_actor_header(client):
    response = client.get("/me")
    assert response.status_code == 401


def test_employee_can_only_see_self(client, employee_headers):
    response = client.get("/employees", headers=employee_headers)
    assert response.status_code == 200
    assert [employee["id"] for employee in response.json()] == [3]

    forbidden = client.get("/employees/4", headers=employee_headers)
    assert forbidden.status_code == 403


def test_manager_scope_contains_self_and_direct_reports(client, manager_headers):
    response = client.get("/employees", headers=manager_headers)
    assert [employee["id"] for employee in response.json()] == [2, 3, 4]

    forbidden = client.get("/employees/6", headers=manager_headers)
    assert forbidden.status_code == 403


def test_admin_can_see_all_employees(client, admin_headers):
    response = client.get("/employees", headers=admin_headers)
    assert len(response.json()) == 6


def test_seed_contains_approval_history(client, employee_headers):
    response = client.get("/approvals", headers=employee_headers)
    assert response.status_code == 200
    assert response.json()[0]["time_entry_id"] == 1
    assert response.json()[0]["decision"] == "approved"


def test_weekly_report_and_csv_remain_role_scoped(client, employee_headers):
    report = client.get("/reports/weekly", headers=employee_headers)
    assert report.status_code == 200
    body = report.json()
    assert body["entry_count"] >= 1
    assert {entry["employee_id"] for entry in body["entries"]} == {3}

    exported = client.get(
        f"/reports/weekly.csv?week_start={body['week_start']}",
        headers=employee_headers,
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert "attachment;" in exported.headers["content-disposition"]
    assert "employee_name" in exported.text
    assert "Jamie Rivera" in exported.text


def test_safe_analytics_query_is_role_scoped_and_declarative(
    client, employee_headers
):
    before = client.get("/time-entries", headers=employee_headers).json()
    response = client.post(
        "/analytics/query",
        headers=employee_headers,
        json={"dimension": "employee", "metric": "hours"},
    )
    assert response.status_code == 200
    assert {row["dimension"] for row in response.json()["rows"]} == {
        "Jamie Rivera"
    }
    after = client.get("/time-entries", headers=employee_headers).json()
    assert after == before


def test_safe_analytics_rejects_sql_text_and_invisible_employee(
    client, employee_headers
):
    injection = client.post(
        "/analytics/query",
        headers=employee_headers,
        json={"dimension": "project; DROP TABLE employees", "metric": "hours"},
    )
    assert injection.status_code == 422

    invisible = client.post(
        "/analytics/query",
        headers=employee_headers,
        json={
            "dimension": "project",
            "metric": "entry_count",
            "employee_id": 4,
        },
    )
    assert invisible.status_code == 403


def test_time_entry_dry_run_does_not_create_business_record(
    client, employee_headers
):
    before = client.get("/time-entries", headers=employee_headers).json()
    response = client.post(
        "/time-entries/dry-run",
        headers=employee_headers,
        json={
            "project_id": 1,
            "work_date": "2026-07-23",
            "hours": "2.50",
            "description": "Reviewed export behavior",
        },
    )
    assert response.status_code == 201
    assert response.json()["dry_run"] is True
    assert response.json()["expires_at"].endswith("Z")
    after = client.get("/time-entries", headers=employee_headers).json()
    assert len(after) == len(before)


def test_personal_suggestions_are_grounded_in_recent_visible_work(
    client, employee_headers
):
    response = client.get(
        "/time-entry-suggestions?target_date=2026-07-30",
        headers=employee_headers,
    )

    assert response.status_code == 200
    suggestion = response.json()[0]
    assert suggestion["project_name"] == "Apollo"
    assert suggestion["target_date"] == "2026-07-30"
    assert suggestion["based_on_entry_id"] in {1, 2}
    assert suggestion["suggested_description"]


def test_batch_dry_run_and_confirmation_are_atomic(client, employee_headers):
    before = client.get("/time-entries", headers=employee_headers).json()
    preview = client.post(
        "/time-entries/batch/dry-run",
        headers=employee_headers,
        json={
            "entries": [
                {
                    "project_id": 1,
                    "work_date": "2026-07-30",
                    "hours": "1.50",
                    "description": "Prepared API examples",
                },
                {
                    "project_id": 1,
                    "work_date": "2026-07-31",
                    "hours": "2.00",
                    "description": "Reviewed API examples",
                },
            ]
        },
    )

    assert preview.status_code == 201
    assert preview.json()["preview"]["count"] == 2
    unchanged = client.get("/time-entries", headers=employee_headers).json()
    assert len(unchanged) == len(before)

    confirmed = client.post(
        f"/actions/{preview.json()['confirmation_token']}/confirm",
        headers=employee_headers,
        json={"confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["result"]["count"] == 2
    after = client.get("/time-entries", headers=employee_headers).json()
    assert len(after) == len(before) + 2


def test_batch_rejects_an_unauthorized_item_without_pending_action(
    client, employee_headers
):
    response = client.post(
        "/time-entries/batch/dry-run",
        headers=employee_headers,
        json={
            "entries": [
                {
                    "project_id": 1,
                    "work_date": "2026-07-30",
                    "hours": "1.00",
                    "description": "Allowed item",
                },
                {
                    "employee_id": 4,
                    "project_id": 1,
                    "work_date": "2026-07-31",
                    "hours": "1.00",
                    "description": "Forbidden item",
                },
            ]
        },
    )

    assert response.status_code == 403


def test_time_entry_requires_explicit_confirmation(client, employee_headers):
    preview = client.post(
        "/time-entries/dry-run",
        headers=employee_headers,
        json={
            "project_id": 1,
            "work_date": "2026-07-23",
            "hours": "2.50",
            "description": "Reviewed export behavior",
        },
    ).json()

    response = client.post(
        f"/actions/{preview['confirmation_token']}/confirm",
        headers=employee_headers,
        json={"confirm": True},
    )
    assert response.status_code == 200
    assert response.json()["result"]["status"] == "draft"

    reuse = client.post(
        f"/actions/{preview['confirmation_token']}/confirm",
        headers=employee_headers,
        json={"confirm": True},
    )
    assert reuse.status_code == 409


def test_employee_cannot_draft_for_another_employee(client, employee_headers):
    response = client.post(
        "/time-entries/dry-run",
        headers=employee_headers,
        json={
            "employee_id": 4,
            "project_id": 1,
            "work_date": "2026-07-23",
            "hours": "1.00",
            "description": "Unauthorized draft",
        },
    )
    assert response.status_code == 403


def test_employee_cannot_approve(client, employee_headers):
    response = client.post(
        "/time-entries/2/approval/dry-run",
        headers=employee_headers,
        json={"decision": "approved"},
    )
    assert response.status_code == 403


def test_manager_can_preview_and_approve_direct_report(client, manager_headers):
    preview = client.post(
        "/time-entries/2/approval/dry-run",
        headers=manager_headers,
        json={"decision": "approved", "comment": "Looks good"},
    )
    assert preview.status_code == 201
    assert (
        client.get("/time-entries/2", headers=manager_headers).json()["status"]
        == "submitted"
    )

    confirmed = client.post(
        f"/actions/{preview.json()['confirmation_token']}/confirm",
        headers=manager_headers,
        json={"confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["result"]["time_entry"]["status"] == "approved"
    approvals = client.get("/approvals", headers=manager_headers).json()
    assert approvals[0]["decision"] == "approved"


def test_manager_cannot_approve_outside_direct_team(client, manager_headers):
    response = client.post(
        "/time-entries/4/approval/dry-run",
        headers=manager_headers,
        json={"decision": "approved"},
    )
    assert response.status_code == 403


def test_admin_can_approve_any_other_employee(client, admin_headers):
    preview = client.post(
        "/time-entries/3/approval/dry-run",
        headers=admin_headers,
        json={"decision": "rejected", "comment": "Please add more detail"},
    )
    assert preview.status_code == 201
    confirmed = client.post(
        f"/actions/{preview.json()['confirmation_token']}/confirm",
        headers=admin_headers,
        json={"confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["result"]["time_entry"]["status"] == "rejected"


def test_confirmation_token_is_bound_to_actor(
    client, employee_headers, manager_headers
):
    preview = client.post(
        "/time-entries/dry-run",
        headers=employee_headers,
        json={
            "project_id": 1,
            "work_date": "2026-07-24",
            "hours": "1.25",
            "description": "Prepared notes",
        },
    ).json()
    response = client.post(
        f"/actions/{preview['confirmation_token']}/confirm",
        headers=manager_headers,
        json={"confirm": True},
    )
    assert response.status_code == 403


def test_confirmation_must_be_explicitly_true(client, employee_headers):
    preview = client.post(
        "/time-entries/dry-run",
        headers=employee_headers,
        json={
            "project_id": 1,
            "work_date": "2026-07-24",
            "hours": "1.25",
            "description": "Prepared notes",
        },
    ).json()
    response = client.post(
        f"/actions/{preview['confirmation_token']}/confirm",
        headers=employee_headers,
        json={"confirm": False},
    )
    assert response.status_code == 422


def test_statistics_are_role_scoped(client, employee_headers, manager_headers):
    employee = client.get(
        "/stats/hours-by-project", headers=employee_headers
    ).json()
    manager = client.get("/stats/hours-by-project", headers=manager_headers).json()
    assert employee == [{"project_id": 1, "project_name": "Apollo", "hours": "13.50"}]
    assert manager == [
        {"project_id": 1, "project_name": "Apollo", "hours": "22.00"}
    ]


def test_draft_lifecycle_requires_fresh_confirmation(client, employee_headers):
    preview = client.post(
        "/time-entries/dry-run", headers=employee_headers,
        json={"project_id": 1, "work_date": "2026-07-30", "hours": "2.00", "description": "Lifecycle draft"},
    ).json()
    entry = client.post(
        f"/actions/{preview['confirmation_token']}/confirm", headers=employee_headers, json={"confirm": True}
    ).json()["result"]
    entry_id = entry["id"]

    update = client.patch(
        f"/time-entries/{entry_id}/dry-run", headers=employee_headers,
        json={"hours": "3.25", "description": "Updated lifecycle draft"},
    ).json()
    assert client.get(f"/time-entries/{entry_id}", headers=employee_headers).json()["hours"] == "2.00"
    changed = client.post(
        f"/actions/{update['confirmation_token']}/confirm", headers=employee_headers, json={"confirm": True}
    ).json()["result"]
    assert changed["hours"] == "3.25"

    for action, expected in (("submit", "submitted"), ("withdraw", "draft")):
        transition = client.post(
            f"/time-entries/{entry_id}/{action}/dry-run", headers=employee_headers
        ).json()
        changed = client.post(
            f"/actions/{transition['confirmation_token']}/confirm", headers=employee_headers, json={"confirm": True}
        ).json()["result"]
        assert changed["status"] == expected

    deletion = client.delete(f"/time-entries/{entry_id}/dry-run", headers=employee_headers).json()
    result = client.post(
        f"/actions/{deletion['confirmation_token']}/confirm", headers=employee_headers, json={"confirm": True}
    ).json()["result"]
    assert result == {"entry_id": entry_id, "deleted": True}


def test_batch_approval_and_admin_audit(client, manager_headers, admin_headers):
    preview = client.post(
        "/time-entries/approvals/batch/dry-run", headers=manager_headers,
        json={"entry_ids": [2, 3], "decision": "approved", "comment": "Batch review"},
    )
    assert preview.status_code == 201
    confirmed = client.post(
        f"/actions/{preview.json()['confirmation_token']}/confirm", headers=manager_headers, json={"confirm": True}
    )
    assert confirmed.json()["result"]["count"] == 2
    assert client.get("/audit-events", headers=manager_headers).status_code == 403
    audit = client.get("/audit-events", headers=admin_headers).json()
    assert audit["items"][0]["action"] == "decide_time_entries"
    assert "details" not in audit["items"][0]


def test_general_csv_export_reuses_role_scope(client, employee_headers):
    response = client.get("/reports/time-entries.csv?status=submitted", headers=employee_headers)
    assert response.status_code == 200
    assert "Jamie Rivera" in response.text
    assert "Refined analytics workspace prototype" not in response.text
