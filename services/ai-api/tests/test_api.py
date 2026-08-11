def test_health_reports_local_mode(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["mode"] == "local"
    assert body["prompt_versions"] == {
        "planner": "1.1.0",
        "composer": "1.1.0",
    }
    assert client.get("/ready").json()["core_api"] == "ok"
    assert int(client.get("/ready").json()["policy_chunks"]) > 0


def test_chat_requires_actor_header(client):
    response = client.post("/chat", json={"message": "List projects"})
    assert response.status_code == 401


def test_preferences_reject_unknown_actor(client):
    response = client.get(
        "/preferences", headers={"X-Actor-ID": "999"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Unknown actor"


def test_greeting_is_conversational_in_local_fallback(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "你好"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["message"].startswith("你好")
    assert body["tool_events"] == []


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
    assert body["confirmation"]["expires_at"].endswith("Z")
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


def test_suggestions_are_read_only_and_grounded_in_personal_history(
    client, fake_core
):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "给我一些今天的智能填报建议"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["type"] == "time_entry_suggestions"
    assert body["data"]["suggestions"][0]["project_name"] == "Apollo"
    assert body["tool_events"][0]["name"] == "get_time_entry_suggestions"
    assert body["confirmation"] is None
    assert fake_core.dry_run_calls == []
    assert fake_core.batch_dry_run_calls == []


def test_explicit_batch_returns_one_confirmation_without_writing(
    client, fake_core
):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={
            "message": (
                "批量填报：2026-07-23 Apollo 2 小时，描述：整理接口文档；"
                "2026-07-24 Apollo 3 小时，描述：补充接口测试"
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confirmation"]["action"] == "create_time_entries"
    assert body["confirmation"]["preview"]["count"] == 2
    assert body["tool_events"][1]["name"] == "dry_run_time_entry_batch"
    assert fake_core.batch_dry_run_calls[0][0] == 3
    assert len(fake_core.batch_dry_run_calls[0][1]["entries"]) == 2


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


def test_manager_sees_pending_question_without_creating_proposal(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "2"},
        json={"message": "Can I approve my team's pending time entries?"},
    )
    body = response.json()
    assert "only inspected the queue" in body["message"]
    assert body["confirmation"] is None


def test_manager_can_create_approval_dry_run_but_not_confirm(client, fake_core):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "2"},
        json={"message": "Approve time entry 2, comment: Looks complete"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confirmation"]["action"] == "decide_time_entry"
    assert body["confirmation"]["preview"]["decision"] == "approved"
    assert body["tool_events"][-1]["name"] == "dry_run_time_entry_approval"
    assert fake_core.approval_dry_run_calls == [
        (2, 2, {"decision": "approved", "comment": "Looks complete"})
    ]


def test_employee_cannot_create_approval_dry_run(client, fake_core):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Approve time entry 2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "cannot approve" in body["message"]
    assert body["confirmation"] is None
    assert fake_core.approval_dry_run_calls == []


def test_stream_emits_stage_tool_and_final_response_without_token_leak(
    client,
):
    with client.stream(
        "POST",
        "/chat/stream",
        headers={"X-Actor-ID": "3"},
        json={"message": "Who am I?"},
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: status" in body
    assert '"stage": "planning"' in body
    assert '"stage": "executing"' in body
    assert "event: tool" in body
    assert '"name": "get_current_actor"' in body
    assert '"stage": "composing"' in body
    assert "event: result" in body
    assert "event: done" in body


def test_stream_intermediate_events_do_not_expose_confirmation_token(client):
    with client.stream(
        "POST",
        "/chat/stream",
        headers={"X-Actor-ID": "2"},
        json={"message": "Approve time entry 2"},
    ) as response:
        body = response.read().decode()

    before_result = body.split("event: result", maxsplit=1)[0]
    assert response.status_code == 200
    assert "approval-demo-token" not in before_result
    assert "approval-demo-token" in body


def test_weekly_report_returns_csv_ready_role_scoped_data(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Generate my weekly report for this week"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["tool_events"][0]["name"] == "get_weekly_report"
    assert body["data"]["type"] == "weekly_report"
    assert body["data"]["entry_count"] == 2
    assert body["confirmation"] is None


def test_comparison_executes_multiple_scoped_read_tools(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Compare Apollo and Beacon hours this week"},
    )
    body = response.json()
    assert response.status_code == 200
    assert [event["name"] for event in body["tool_events"]] == [
        "list_projects",
        "list_time_entries",
        "list_time_entries",
    ]
    assert body["data"]["type"] == "comparison"
    assert [row["label"] for row in body["data"]["rows"]] == [
        "Apollo",
        "Beacon",
    ]
    assert body["confirmation"] is None


def test_comparison_rejects_an_unauthorized_project_before_querying_it(
    client,
):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "Compare Apollo and Orion hours this week"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["confirmation"] is None
    assert "outside your authorized scope" in body["message"]
    assert [event["name"] for event in body["tool_events"]] == ["list_projects"]


def test_preferences_require_dry_run_and_actor_bound_confirmation(client):
    defaults = client.get("/preferences", headers={"X-Actor-ID": "3"}).json()
    assert defaults["history_enabled"] is True
    preview = client.post(
        "/preferences/dry-run",
        headers={"X-Actor-ID": "3"},
        json={
            "history_enabled": False,
            "preferred_language": "zh",
            "preferred_project_id": 1,
        },
    )
    assert preview.status_code == 201
    assert client.get("/preferences", headers={"X-Actor-ID": "3"}).json() == defaults
    token = preview.json()["confirmation_token"]
    forbidden = client.post(
        f"/preferences/actions/{token}/confirm",
        headers={"X-Actor-ID": "2"},
        json={"confirm": True},
    )
    assert forbidden.status_code == 403
    confirmed = client.post(
        f"/preferences/actions/{token}/confirm",
        headers={"X-Actor-ID": "3"},
        json={"confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["result"]["history_enabled"] is False
    assert confirmed.json()["result"]["preferred_language"] == "zh"


def test_preferred_project_must_be_currently_visible(client):
    response = client.post(
        "/preferences/dry-run",
        headers={"X-Actor-ID": "3"},
        json={"preferred_project_id": 999},
    )
    assert response.status_code == 403


def test_private_state_deletion_is_also_two_step(client):
    preview = client.post(
        "/preferences/delete/dry-run", headers={"X-Actor-ID": "3"}
    )
    assert preview.status_code == 201
    token = preview.json()["confirmation_token"]
    confirmed = client.post(
        f"/preferences/actions/{token}/confirm",
        headers={"X-Actor-ID": "3"},
        json={"confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["result"]["deleted"] is True
    reset = client.get("/preferences", headers={"X-Actor-ID": "3"}).json()
    assert reset["preferred_language"] == "auto"


def test_safe_sql_agent_executes_only_declarative_role_scoped_spec(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={"message": "SQL analysis: group hours by status this week"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["tool_events"][-1]["name"] == "execute_safe_analytics_query"
    assert body["data"]["type"] == "safe_sql_analysis"
    assert body["data"]["query_spec"]["dimension"] == "status"
    assert "sql" not in body["data"]["query_spec"]
    assert body["confirmation"] is None


def test_safe_sql_agent_refuses_user_supplied_sql_text(client):
    response = client.post(
        "/chat",
        headers={"X-Actor-ID": "3"},
        json={
            "message": "SQL analysis: SELECT * FROM employees; DROP TABLE employees"
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert "cannot accept or generate raw SQL" in body["message"]
    assert body["tool_events"] == []
    assert body["confirmation"] is None
