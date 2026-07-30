def test_health_reports_local_mode(client):
    assert client.get("/health").json() == {"status": "ok", "mode": "local"}
    assert client.get("/ready").json()["core_api"] == "ok"
    assert int(client.get("/ready").json()["policy_chunks"]) > 0


def test_chat_requires_actor_header(client):
    response = client.post("/chat", json={"message": "List projects"})
    assert response.status_code == 401


def test_lists_role_scoped_projects(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Which projects can I see?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"][0]["name"] == "Apollo"
    assert body["tool_events"][0]["name"] == "list_projects"


def test_answers_policy_question_with_structured_citation(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "What is the weekly time submission deadline policy?"},
    )

    body = response.json()
    assert "12:00 noon" in body["message"]
    assert body["tool_events"][0]["name"] == "retrieve_policy"
    assert body["citations"][0]["source_id"] == "time-reporting"
    assert body["citations"][0]["section"] == "Weekly submission deadline"


def test_explicit_policy_question_about_approval_uses_policy_retrieval(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "What does the time reporting policy say about approval?"},
    )

    body = response.json()
    assert body["tool_events"][0]["name"] == "retrieve_policy"
    assert body["citations"][0]["source_id"] == "time-reporting"


def test_shows_current_role_scoped_profile(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Who am I?"},
    )
    body = response.json()
    assert "Jamie Rivera" in body["message"]
    assert body["data"]["role"] == "employee"
    assert body["tool_events"][0]["name"] == "get_current_actor"


def test_lists_visible_departments(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "我能看到哪些部门？"},
    )
    body = response.json()
    assert body["data"] == [
        {"id": 1, "name": "Product Engineering", "code": "ENG"}
    ]
    assert body["tool_events"][0]["name"] == "list_departments"


def test_employee_list_remains_role_scoped(client):
    employee_response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "List employees"},
    )
    manager_response = client.post(
        "/chat",
        headers={"X-Actor-ID": "2"},
        json={"message": "List my team members"},
    )
    assert [item["name"] for item in employee_response.json()["data"]] == [
        "Jamie Rivera"
    ]
    assert [item["name"] for item in manager_response.json()["data"]] == [
        "Morgan Lee",
        "Jamie Rivera",
    ]


def test_lists_visible_project_members_with_names(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Who is on the Apollo project?"},
    )
    body = response.json()
    assert body["data"][0]["employee_name"] == "Jamie Rivera"
    assert [event["name"] for event in body["tool_events"]] == [
        "list_projects",
        "list_project_members",
        "list_employees",
    ]


def test_lists_recent_time_entries_with_limit_and_status(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Show my last 1 submitted time entries"},
    )
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["status"] == "submitted"
    assert body["tool_events"][1]["input"]["limit"] == 1


def test_supports_last_week_date_range_for_entry_lists(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "显示我上周的工时记录"},
    )
    filters = response.json()["tool_events"][1]["input"]
    assert filters["start_date"] == "2026-07-13"
    assert filters["end_date"] == "2026-07-19"


def test_returns_role_scoped_status_summary(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Show my hours status summary"},
    )
    body = response.json()
    assert "13.50 hours" in body["message"]
    assert body["data"]["submitted_hours"] == "6.00"
    assert body["tool_events"][0]["name"] == "get_time_summary"


def test_session_supports_project_follow_up(client):
    first = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "How many hours did I log on Apollo this week?"},
    ).json()
    second = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={
            "message": "What about Beacon?",
            "session_id": first["session_id"],
        },
    ).json()

    assert second["session_id"] == first["session_id"]
    assert "0.00 hours on Beacon" in second["message"]
    assert second["context"] == {
        "turn_count": 2,
        "actor_role": "employee",
        "department_names": ["Product Engineering"],
        "recent_project_names": ["Apollo"],
    }


def test_session_follow_up_inherits_safe_read_filters(client):
    first = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "How many hours did I log on Apollo this week?"},
    ).json()
    second = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={
            "message": "Only show submitted entries.",
            "session_id": first["session_id"],
        },
    ).json()

    filters = second["tool_events"][1]["input"]
    assert filters["project_id"] == 1
    assert filters["status"] == "submitted"
    assert filters["start_date"] == "2026-07-20"
    assert filters["end_date"] == "2026-07-22"


def test_session_never_inherits_missing_write_fields(client, fake_core):
    first = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "How many hours did I log on Apollo this week?"},
    ).json()
    second = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={
            "message": "Draft 2 hours: follow-up work",
            "session_id": first["session_id"],
        },
    ).json()

    assert "project, work_date" in second["message"]
    assert second["confirmation"] is None
    assert fake_core.dry_run_calls == []


def test_session_is_bound_to_actor(client):
    first = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Who am I?"},
    ).json()
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "2"},
        json={
            "message": "Who am I?",
            "session_id": first["session_id"],
        },
    )
    assert response.status_code == 403


def test_recent_project_attribute_can_resolve_query(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "How many hours on my recent project this week?"},
    )
    assert "13.50 hours on Apollo" in response.json()["message"]


def test_sums_hours_for_project_this_week(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "How many hours did I log on Apollo this week?"},
    )
    body = response.json()
    assert "13.50 hours" in body["message"]
    assert body["data"]["hours"] == "13.50"
    assert [event["name"] for event in body["tool_events"]] == [
        "list_projects",
        "list_time_entries",
    ]


def test_returns_monthly_chart_data(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Show monthly hours by project as a chart"},
    )
    chart = response.json()["data"]
    assert chart["type"] == "bar"
    assert chart["rows"] == [
        {"month": "2026-07", "project": "Apollo", "hours": "13.50"}
    ]


def test_incomplete_draft_asks_for_exact_fields_without_calling_core(
    client, fake_core
):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Draft my remaining time this week"},
    )
    assert response.status_code == 200
    assert "exact values" in response.json()["message"]
    assert fake_core.dry_run_calls == []


def test_complete_draft_returns_confirmation_card_but_does_not_confirm(
    client, fake_core
):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={
            "message": (
                "Draft 2.5 hours on Apollo for 2026-07-22: "
                "Reviewed export behavior"
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["confirmation"]["confirmation_token"] == "demo-token"
    assert body["confirmation"]["confirm_path"].endswith(
        "/demo-token/confirm"
    )
    assert fake_core.dry_run_calls == [
        (
            3,
            {
                "project_id": 1,
                "work_date": "2026-07-22",
                "hours": "2.5",
                "description": "Reviewed export behavior",
            },
        )
    ]


def test_chinese_time_entry_request_is_a_dry_run(client, fake_core):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={
            "message": (
                "帮我填报 2026-07-29 Apollo 项目 2 小时，"
                "备注：客户访谈"
            )
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["confirmation"]["confirmation_token"] == "demo-token"
    assert body["tool_events"][1]["name"] == "dry_run_time_entry"
    assert fake_core.dry_run_calls == [
        (
            3,
            {
                "project_id": 1,
                "work_date": "2026-07-29",
                "hours": "2",
                "description": "客户访谈",
            },
        )
    ]


def test_employee_approval_question_is_read_only(client, fake_core):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Can I approve my team's pending time entries?"},
    )
    body = response.json()
    assert "cannot approve" in body["message"]
    assert body["confirmation"] is None
    assert fake_core.dry_run_calls == []


def test_manager_sees_pending_but_ai_api_does_not_approve(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "2"},
        json={"message": "Can I approve my team's pending time entries?"},
    )
    body = response.json()
    assert "read-only for approvals" in body["message"]
    assert body["confirmation"] is None
