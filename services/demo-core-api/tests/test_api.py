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
    after = client.get("/time-entries", headers=employee_headers).json()
    assert len(after) == len(before)


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
