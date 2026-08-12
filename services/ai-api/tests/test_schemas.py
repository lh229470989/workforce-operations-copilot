from app.schemas import AgentPlan


def test_agent_plan_normalizes_provider_empty_object_resolution():
    plan = AgentPlan.model_validate(
        {"intent": "greeting", "field_resolutions": {}}
    )

    assert plan.field_resolutions == []


def test_agent_plan_defaults_unknown_provider_relation_to_independent():
    plan = AgentPlan.model_validate(
        {"intent": "greeting", "conversation_relation": {}}
    )

    assert plan.conversation_relation == "independent"


def test_agent_plan_normalizes_dashscope_empty_optional_fields():
    plan = AgentPlan.model_validate(
        {
            "intent": "greeting",
            "inherit_fields": "",
            "time_entry_ids": {},
            "approval_decision": "",
            "lifecycle_action": "",
        }
    )

    assert plan.inherit_fields == []
    assert plan.time_entry_ids == []
    assert plan.approval_decision is None
    assert plan.lifecycle_action is None
