from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Callable

from fastapi import FastAPI, Header, HTTPException, Response

from .agent import build_agent
from .config import Settings
from .conversation_context import build_planner_context, summarize_context
from .core_client import CoreAPIClient
from .knowledge_base import PolicyKnowledgeBase
from .observability import MetricsRegistry, install_observability
from .planner import LocalPlanner, OpenAIPlanner, Planner
from .schemas import ChatRequest, ChatResponse
from .session_memory import SessionActorMismatchError, SessionMemory


def create_app(
    settings: Settings | None = None,
    *,
    core_client: CoreAPIClient | None = None,
    planner: Planner | None = None,
    session_memory: SessionMemory | None = None,
    knowledge_base: PolicyKnowledgeBase | None = None,
    today_provider: Callable[[], date] = date.today,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    mode = resolved_settings.resolved_mode
    if mode == "openai" and not resolved_settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required when AI_MODE=openai")

    core = core_client or CoreAPIClient(resolved_settings.core_api_base_url)
    memory = session_memory or SessionMemory(
        ttl_seconds=resolved_settings.session_ttl_seconds,
        max_turns=resolved_settings.session_max_turns,
    )
    policies = knowledge_base or PolicyKnowledgeBase(
        Path(resolved_settings.knowledge_base_path)
    )
    metrics = MetricsRegistry()
    selected_planner = planner
    if selected_planner is None:
        selected_planner = (
            OpenAIPlanner(
                resolved_settings.openai_api_key or "",
                resolved_settings.openai_model,
            )
            if mode == "openai"
            else LocalPlanner()
        )
    graph = build_agent(
        selected_planner,
        core,
        mode=mode,
        knowledge_base=policies,
        today_provider=today_provider,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await selected_planner.close()
        await core.close()

    app = FastAPI(
        title="AcmeWorks AI API",
        version="0.1.0",
        description=(
            "Role-aware LangGraph orchestration for fictional AcmeWorks data. "
            "Only read tools and dry-run time-entry drafting are exposed."
        ),
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.core_client = core
    app.state.planner = selected_planner
    app.state.agent = graph
    app.state.session_memory = memory
    app.state.knowledge_base = policies
    app.state.metrics = metrics
    install_observability(app, metrics)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": mode}

    @app.get("/ready", tags=["system"])
    async def ready() -> dict[str, str]:
        await core.health()
        return {
            "status": "ready",
            "core_api": "ok",
            "mode": mode,
            "policy_chunks": str(len(policies.chunks)),
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
        planner_context = await build_planner_context(core, actor_id, session)
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

    return app


app = create_app()
