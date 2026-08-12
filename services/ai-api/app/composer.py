import json
import logging
from contextvars import ContextVar
from hashlib import sha256
from typing import Any, Protocol

from openai import AsyncOpenAI

from .schemas import AgentPlan, ExecutionResult, PlannerContext

logger = logging.getLogger(__name__)
_stream_sink: ContextVar[Any | None] = ContextVar("composer_stream_sink", default=None)


def set_stream_sink(sink: Any):
    """Attach one request-local delta callback."""

    return _stream_sink.set(sink)


def reset_stream_sink(token: Any) -> None:
    _stream_sink.reset(token)


async def _emit_delta(delta: str) -> None:
    sink = _stream_sink.get()
    if sink is not None and delta:
        await sink(delta)


class ResponseComposer(Protocol):
    """Turn an authorized execution result into the user-facing answer."""

    async def compose(
        self,
        message: str,
        plan: AgentPlan,
        result: ExecutionResult,
        context: PlannerContext | None,
        actor_id: int,
    ) -> str: ...

    async def close(self) -> None: ...


class LocalComposer:
    """Deterministic fallback used when no model endpoint is configured."""

    async def compose(
        self,
        message: str,
        plan: AgentPlan,
        result: ExecutionResult,
        context: PlannerContext | None,
        actor_id: int,
    ) -> str:
        await _emit_delta(result.message)
        return result.message

    async def close(self) -> None:
        return None


class OpenAIComposer:
    """Generate natural answers from server-authorized, synthetic tool data."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        *,
        instructions: str,
    ) -> None:
        client_options = {"api_key": api_key}
        if base_url:
            client_options["base_url"] = base_url
        self._client = AsyncOpenAI(
            **client_options,
            timeout=45.0,
            max_retries=1,
        )
        self._model = model
        self._instructions = instructions
        self._is_dashscope = bool(
            base_url
            and (
                "dashscope." in base_url
                or ".maas.aliyuncs.com" in base_url
            )
        )

    async def close(self) -> None:
        await self._client.close()

    @staticmethod
    def _safe_context(context: PlannerContext | None) -> dict[str, Any]:
        if context is None:
            return {}
        # Recent dialogue makes the response conversational. Authoritative
        # attributes are deliberately reduced to fields useful for wording.
        return {
            "actor": {
                key: context.actor.get(key)
                for key in ("name", "role", "title")
            },
            "departments": [item.get("name") for item in context.departments],
            "recent_projects": context.recent_project_names,
            "user_preferences": context.preferences,
            "recent_dialogue": [
                {
                    "user": turn.user_message,
                    "assistant": turn.assistant_message,
                }
                for turn in context.turns[-6:]
            ],
        }

    @staticmethod
    def _safe_result(result: ExecutionResult) -> dict[str, Any]:
        # Confirmation tokens authorize writes and must never be sent to a
        # model provider. The model only needs the preview to explain dry-run.
        confirmation = None
        if result.confirmation is not None:
            confirmation = {
                "action": result.confirmation.action,
                "preview": result.confirmation.preview,
                "expires_at": result.confirmation.expires_at.isoformat(),
            }
        return {
            "fallback_message": result.message,
            "data": result.data,
            "citations": [
                citation.model_dump(mode="json")
                for citation in result.citations
            ],
            "tools": [
                {"name": event.name, "input": event.input}
                for event in result.tool_events
            ],
            "dry_run_confirmation": confirmation,
        }

    @staticmethod
    def _visualization_message(
        message: str, plan: AgentPlan, result: ExecutionResult
    ) -> str | None:
        """Keep chart prose deterministic because the web owns rendering."""

        data = result.data
        if (
            plan.intent != "monthly_chart"
            or not isinstance(data, dict)
            or data.get("type") != "bar"
        ):
            return None
        rows = data.get("rows")
        row_count = len(rows) if isinstance(rows, list) else 0
        is_chinese = any(
            "\u4e00" <= character <= "\u9fff" for character in message
        )
        if is_chinese:
            return (
                f"已生成按项目统计的月度工时图表，共 {row_count} 个数据项。"
                "图表数据来自当前角色可见的工时记录。"
            )
        return (
            f"I generated the monthly hours-by-project chart with {row_count} "
            "data point(s), using only records visible to your current role."
        )

    @staticmethod
    def _structured_ui_message(
        message: str, plan: AgentPlan, result: ExecutionResult
    ) -> str | None:
        """Keep tabular/link wording aligned with trusted UI-owned data."""

        data = result.data
        is_chinese = any("\u4e00" <= character <= "\u9fff" for character in message)
        if plan.intent == "time_entries" and isinstance(data, list):
            count = len(data)
            if is_chinese:
                return f"在你当前角色的权限范围内，共找到 {count} 条工时记录。"
            return f"I found {count} time entries within your current role scope."
        if not isinstance(data, dict) or data.get("type") != "report_export":
            return None
        count = data.get("row_count", 0)
        if is_chinese:
            return f"已准备好包含 {count} 条匹配工时记录的权限范围内 CSV 下载。"
        return f"Your role-scoped CSV export is ready with {count} matching time entries."

    async def compose(
        self,
        message: str,
        plan: AgentPlan,
        result: ExecutionResult,
        context: PlannerContext | None,
        actor_id: int,
    ) -> str:
        visualization_message = self._visualization_message(
            message, plan, result
        )
        if visualization_message is not None:
            await _emit_delta(visualization_message)
            return visualization_message
        structured_message = self._structured_ui_message(message, plan, result)
        if structured_message is not None:
            await _emit_delta(structured_message)
            return structured_message
        payload = {
            "user_message": message,
            "plan": plan.model_dump(mode="json"),
            "context": self._safe_context(context),
            "authorized_execution": self._safe_result(result),
        }
        safety_identifier = sha256(
            f"acmeworks-demo:{actor_id}".encode()
        ).hexdigest()[:32]
        request: dict[str, Any] = {
            "model": self._model,
            "instructions": self._instructions,
            # Tool results may contain Python dates or Decimals after local
            # execution. String conversion keeps the provider payload valid
            # without changing the structured response returned to the UI.
            "input": json.dumps(payload, ensure_ascii=False, default=str),
            "max_output_tokens": 800,
            "store": False,
        }
        if getattr(self, "_is_dashscope", False):
            # Keep provider-specific requests intentionally minimal. Disabling
            # thinking reduces latency for the final grounded wording pass.
            request["extra_body"] = {"enable_thinking": False}
        else:
            request.update(
                {
                    "reasoning": {"effort": "low"},
                    "safety_identifier": safety_identifier,
                    "verbosity": "low",
                }
            )
        try:
            if _stream_sink.get() is None:
                response = await self._client.responses.create(**request)
                answer = response.output_text.strip()
            else:
                parts: list[str] = []
                async with self._client.responses.stream(**request) as stream:
                    async for event in stream:
                        if event.type == "response.output_text.delta":
                            parts.append(event.delta)
                            await _emit_delta(event.delta)
                answer = "".join(parts).strip()
            return answer or result.message
        except Exception as exc:
            # Keep the demo available when the external model is unavailable.
            # Prompts and workforce payloads are intentionally absent from logs.
            logger.warning(
                "llm_composition_failed error_type=%s", type(exc).__name__
            )
            await _emit_delta(result.message)
            return result.message
