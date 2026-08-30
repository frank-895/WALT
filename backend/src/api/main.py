from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.demo import (
    DaytonaSandboxProvider,
    DemoService,
    PydanticVoiceRuntime,
    SandboxProvider,
    VoiceRuntime,
    demo_router,
)
from api.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    sandbox_provider: SandboxProvider | None = None,
    voice_runtime: VoiceRuntime | None = None,
) -> FastAPI:
    """Create the WALT API with lifespan-owned external resources.

    Args:
        settings: Optional explicit settings for tests.
        sandbox_provider: Optional sandbox provider implementation.
        voice_runtime: Optional Realtime sideband implementation.

    Returns:
        Configured FastAPI application.
    """
    application_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Own the session registry and provider connection pools."""
        sandboxes = sandbox_provider or DaytonaSandboxProvider(application_settings)
        voice = voice_runtime or PydanticVoiceRuntime(application_settings)
        service = DemoService(application_settings, sandboxes, voice)
        application.state.demo_service = service
        await service.start()
        try:
            yield
        finally:
            await service.close()

    application = FastAPI(title="WALT API", lifespan=lifespan)
    application.include_router(demo_router)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        """Report whether the API is ready to receive requests."""
        return {"status": "ok"}

    return application


app = create_app()
