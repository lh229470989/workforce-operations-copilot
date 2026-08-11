import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import date, datetime
import json
from pathlib import Path
from typing import Annotated, Callable
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import StreamingResponse

from .agent import build_agent
from .composer import (
    LocalComposer,
    OpenAIComposer,
    ResponseComposer,
    reset_stream_sink,
    set_stream_sink,
)
from .config import Settings
from .conversation_context import build_planner_context, summarize_context
from .core_client import CoreAPIClient
from .knowledge_base import PolicyKnowledgeBase
from .observability import MetricsRegistry, install_observability
from .planner import LocalPlanner, OpenAIPlanner, Planner
from .prompt_registry import PromptRegistry
from .persistent_state import PersistentStateStore
from .schemas import (
    ChatRequest,
    ChatResponse,
    PreferenceConfirmRequest,
    PreferenceUpdateRequest,
)
from .session_memory import SessionActorMismatchError, SessionMemory


def create_app(
    settings: Settings | None = None,
    *,
    core_client: CoreAPIClient | None = None,
    planner: Planner | None = None,
    composer: ResponseComposer | None = None,
    session_memory: SessionMemory | None = None,
    knowledge_base: PolicyKnowledgeBase | None = None,
    today_provider: Callable[[], date] | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    business_zone = ZoneInfo(resolved_settings.business_timezone)
    resolved_today_provider = today_provider or (
        lambda: datetime.now(business_zone).date()
    )
    mode = resolved_settings.resolved_mode
    if mode == "openai" and not resolved_settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when AI_MODE=openai")

    core = core_client or CoreAPIClient(resolved_settings.core_api_base_url)
    memory = session_memory or PersistentStateStore(
        resolved_settings.state_database_path,
        ttl_seconds=resolved_settings.session_ttl_seconds,
        max_turns=resolved_settings.session_max_turns,
    )
    policies = knowledge_base or PolicyKnowledgeBase(
        Path(resolved_settings.knowledge_base_path)
    )
    prompts = PromptRegistry(Path(resolved_settings.prompt_path))
    metrics = MetricsRegistry()
    selected_planner = planner
    if selected_planner is None:
        selected_planner = (
            OpenAIPlanner(
                resolved_settings.openai_api_key or "",
                resolved_settings.openai_planner_model
                or resolved_settings.openai_model,
                resolved_settings.openai_base_url,
                instructions=prompts.get("planner").text,
            )
            if mode == "openai"
            else LocalPlanner()
        )
    selected_composer = composer
    if selected_composer is None:
        selected_composer = (
            OpenAIComposer(
                resolved_settings.openai_api_key or "",
                resolved_settings.openai_composer_model
                or resolved_settings.openai_model,
                resolved_settings.openai_base_url,
                instructions=prompts.get("composer").text,
            )
            if mode == "openai"
            else LocalComposer()
        )
    graph = build_agent(
        selected_planner,
        core,
        mode=mode,
        composer=selected_composer,
        knowledge_base=policies,
        today_provider=resolved_today_provider,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        cleanup_task = None
        if hasattr(memory, "cleanup_expired"):
            await memory.cleanup_expired()

            async def cleanup_private_state() -> None:
                interval = min(
                    60.0,
                    max(1.0, resolved_settings.session_ttl_seconds / 2),
                )
                while True:
                    await asyncio.sleep(interval)
                    await memory.cleanup_expired()

            cleanup_task = asyncio.create_task(cleanup_private_state())
        try:
            yield
        finally:
            if cleanup_task is not None:
                cleanup_task.cancel()
                with suppress(asyncio.CancelledError):
                    await cleanup_task
            await selected_planner.close()
            await selected_composer.close()
            await core.close()

    app = FastAPI(
        title="AcmeWorks AI API",
        version="0.1.0",
        description=(
            "Role-aware LangGraph orchestration for fictional AcmeWorks data. "
            "Only scoped reads and dry-run write proposals are exposed."
        ),
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.core_client = core
    app.state.planner = selected_planner
    app.state.composer = selected_composer
    app.state.agent = graph
    app.state.session_memory = memory
    app.state.knowledge_base = policies
    app.state.prompt_registry = prompts
    app.state.metrics = metrics
    install_observability(app, metrics)

    async def actor_preferences(actor_id: int) -> dict[str, object]:
        if hasattr(memory, "get_preferences"):
            return await memory.get_preferences(actor_id)
        return {
            "actor_id": actor_id,
            "history_enabled": True,
            "preferred_language": "auto",
            "preferred_project_id": None,
            "response_detail": "standard",
            "report_format": "summary",
        }

    async def require_known_actor(actor_id: int) -> None:
        """Validate demo identity through the authoritative Core API."""

        await core.get_me(actor_id)

    async def require_admin_actor(actor_id: int) -> None:
        actor = await core.get_me(actor_id)
        if actor.get("role") != "admin":
            raise HTTPException(403, "Admin role required")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "mode": mode,
            "prompt_versions": prompts.versions,
        }

    @app.get("/ready", tags=["system"])
    async def ready() -> dict[str, object]:
        await core.health()
        return {
            "status": "ready",
            "core_api": "ok",
            "mode": mode,
            "policy_chunks": str(len(policies.chunks)),
            "prompt_versions": prompts.versions,
        }

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return Response(
            metrics.render_prometheus(),
            media_type="text/plain; version=0.0.4",
        )

    @app.get("/observability", tags=["system"])
    async def observability() -> dict[str, object]:
        return metrics.snapshot()

    @app.get("/knowledge", tags=["knowledge"])
    async def knowledge_status(
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> dict[str, object]:
        if actor_id is None:
            raise HTTPException(401, "X-Actor-ID header is required")
        await require_admin_actor(actor_id)
        return {
            "documents": len({chunk.source_id for chunk in policies.chunks}),
            "chunks": len(policies.chunks),
            "path": "knowledge-base",
        }

    @app.post("/knowledge/reload", tags=["knowledge"])
    async def reload_knowledge(
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> dict[str, object]:
        if actor_id is None:
            raise HTTPException(401, "X-Actor-ID header is required")
        await require_admin_actor(actor_id)
        return {"status": "reloaded", **policies.reload()}

    @app.get("/preferences", tags=["privacy"])
    async def get_preferences(
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> dict[str, object]:
        if actor_id is None:
            raise HTTPException(401, "X-Actor-ID header is required")
        await require_known_actor(actor_id)
        return await actor_preferences(actor_id)

    @app.post("/preferences/dry-run", status_code=201, tags=["privacy"])
    async def dry_run_preferences(
        body: PreferenceUpdateRequest,
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> dict[str, object]:
        if actor_id is None:
            raise HTTPException(401, "X-Actor-ID header is required")
        await require_known_actor(actor_id)
        if not hasattr(memory, "prepare_preferences"):
            raise HTTPException(501, "Persistent preferences are unavailable")
        updates = body.model_dump(exclude_none=True)
        clear_project = updates.pop("clear_preferred_project", False)
        if clear_project:
            updates["preferred_project_id"] = None
        project_id = updates.get("preferred_project_id")
        if project_id is not None:
            visible_projects = await core.list_projects(actor_id)
            if project_id not in {project["id"] for project in visible_projects}:
                raise HTTPException(
                    403, "Preferred project is outside the actor's current scope"
                )
        return await memory.prepare_preferences(actor_id, updates)

    @app.post("/preferences/delete/dry-run", status_code=201, tags=["privacy"])
    async def dry_run_private_state_deletion(
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> dict[str, object]:
        if actor_id is None:
            raise HTTPException(401, "X-Actor-ID header is required")
        await require_known_actor(actor_id)
        if not hasattr(memory, "prepare_state_deletion"):
            raise HTTPException(501, "Persistent preferences are unavailable")
        return await memory.prepare_state_deletion(actor_id)

    @app.post("/preferences/actions/{token}/confirm", tags=["privacy"])
    async def confirm_preference_action(
        token: str,
        _: PreferenceConfirmRequest,
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> dict[str, object]:
        if actor_id is None:
            raise HTTPException(401, "X-Actor-ID header is required")
        await require_known_actor(actor_id)
        if not hasattr(memory, "confirm_preferences"):
            raise HTTPException(501, "Persistent preferences are unavailable")
        try:
            result = await memory.confirm_preferences(actor_id, token)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        except TimeoutError as exc:
            raise HTTPException(410, str(exc)) from exc
        return {"action": "preferences_confirmed", "result": result}

    @app.post("/chat", response_model=ChatResponse, tags=["chat"])
    async def chat(
        body: ChatRequest,
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> ChatResponse:
        if actor_id is None:
            raise HTTPException(
                status_code=401, detail="X-Actor-ID header is required"
            )
        requested_session_id = (
            str(body.session_id) if body.session_id is not None else None
        )
        try:
            session = await memory.open(actor_id, requested_session_id)
        except SessionActorMismatchError as exc:
            raise HTTPException(
                status_code=403,
                detail="Conversation session belongs to another demo actor",
            ) from exc
        planner_context = await build_planner_context(
            core, actor_id, session, await actor_preferences(actor_id)
        )
        state = await graph.ainvoke(
            {
                "message": body.message,
                "actor_id": actor_id,
                "planner_context": planner_context,
            }
        )
        metrics.observe_chat(state["plan"].intent)
        response = state["response"].model_copy(
            update={
                "session_id": session.session_id,
                "context": summarize_context(planner_context),
            }
        )
        await memory.append(
            session.session_id,
            actor_id,
            user_message=body.message,
            assistant_message=response.message,
            plan=state["plan"],
        )
        return response

    @app.post("/chat/stream", tags=["chat"])
    async def chat_stream(
        body: ChatRequest,
        actor_id: Annotated[int | None, Header(alias="X-Actor-ID")] = None,
    ) -> StreamingResponse:
        """Stream safe stage metadata, then the normal structured response.

        Tool payloads and confirmation tokens are deliberately excluded from
        intermediate events. The token appears only in the final response,
        exactly as it does for the existing non-streaming endpoint.
        """

        if actor_id is None:
            raise HTTPException(
                status_code=401, detail="X-Actor-ID header is required"
            )
        requested_session_id = (
            str(body.session_id) if body.session_id is not None else None
        )
        try:
            session = await memory.open(actor_id, requested_session_id)
        except SessionActorMismatchError as exc:
            raise HTTPException(
                status_code=403,
                detail="Conversation session belongs to another demo actor",
            ) from exc
        planner_context = await build_planner_context(
            core, actor_id, session, await actor_preferences(actor_id)
        )

        def event(name: str, payload: object) -> str:
            serialized = json.dumps(payload, ensure_ascii=False, default=str)
            return f"event: {name}\ndata: {serialized}\n\n"

        async def generate():
            queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

            async def produce() -> None:
                plan = None
                sink_token = set_stream_sink(
                    lambda delta: queue.put(("delta", {"text": delta}))
                )
                await queue.put(
                    (
                        "status",
                        {"stage": "planning", "message": "Understanding request"},
                    )
                )
                try:
                    async for update in graph.astream(
                        {
                            "message": body.message,
                            "actor_id": actor_id,
                            "planner_context": planner_context,
                        },
                        stream_mode="updates",
                    ):
                        if "plan" in update:
                            plan = update["plan"]["plan"]
                            await queue.put(
                                (
                                    "status",
                                    {
                                        "stage": "executing",
                                        "message": "Running authorized tools",
                                        "intent": plan.intent,
                                    },
                                )
                            )
                        if "execute" in update:
                            result = update["execute"]["result"]
                            for tool in result.tool_events:
                                await queue.put(
                                    (
                                        "tool",
                                        {"name": tool.name, "status": tool.status},
                                    )
                                )
                            await queue.put(
                                (
                                    "status",
                                    {
                                        "stage": "composing",
                                        "message": "Grounding answer",
                                    },
                                )
                            )
                        if "compose" in update:
                            if plan is None:
                                raise RuntimeError(
                                    "Agent stream completed without a plan"
                                )
                            metrics.observe_chat(plan.intent)
                            response = update["compose"]["response"].model_copy(
                                update={
                                    "session_id": session.session_id,
                                    "context": summarize_context(planner_context),
                                }
                            )
                            await memory.append(
                                session.session_id,
                                actor_id,
                                user_message=body.message,
                                assistant_message=response.message,
                                plan=plan,
                            )
                            await queue.put(
                                ("result", response.model_dump(mode="json"))
                            )
                    await queue.put(("done", {"ok": True}))
                except Exception as exc:
                    await queue.put(
                        (
                            "error",
                            {
                                "detail": "Agent stream failed",
                                "type": type(exc).__name__,
                            },
                        )
                    )
                finally:
                    reset_stream_sink(sink_token)

            producer = asyncio.create_task(produce())
            try:
                while True:
                    name, payload = await queue.get()
                    yield event(name, payload)
                    if name in {"done", "error"}:
                        break
            finally:
                await producer

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
