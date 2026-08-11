import shutil
from pathlib import Path

import pytest

from app.config import DEFAULT_PROMPT_PATH
from app.prompt_registry import PromptRegistry


def test_checked_in_prompt_manifest_loads_named_versions():
    registry = PromptRegistry(Path(DEFAULT_PROMPT_PATH))

    assert registry.versions == {"planner": "1.1.0", "composer": "1.1.0"}
    assert "Return exactly one AgentPlan" in registry.get("planner").text
    assert "source of truth" in registry.get("composer").text


def test_prompt_registry_fails_closed_when_a_versioned_file_drifts(tmp_path):
    prompt_copy = tmp_path / "prompts"
    shutil.copytree(DEFAULT_PROMPT_PATH, prompt_copy)
    planner_path = prompt_copy / "planner-v1.1.txt"
    planner_path.write_text(planner_path.read_text() + "\nunreviewed change\n")

    with pytest.raises(ValueError, match="Prompt checksum mismatch: planner"):
        PromptRegistry(prompt_copy)
