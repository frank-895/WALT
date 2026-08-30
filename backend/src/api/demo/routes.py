from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from api.demo.models import (
    DemoConflictError,
    DemoNotFoundError,
    DemoSessionCreated,
    DemoSessionState,
    VoiceAnswer,
)
from api.demo.providers import ProviderConfigurationError
from api.demo.service import DemoService

router = APIRouter(prefix="/api/demo-sessions", tags=["demo sessions"])


def get_demo_service(request: Request) -> DemoService:
    """Resolve the lifespan-owned demo service.

    Args:
        request: Active FastAPI request.

    Returns:
        Shared application demo service.
    """
    return request.app.state.demo_service


DemoServiceDependency = Annotated[DemoService, Depends(get_demo_service)]


@router.post("", response_model=DemoSessionCreated, status_code=status.HTTP_201_CREATED)
async def create_demo_session(service: DemoServiceDependency) -> DemoSessionCreated:
    """Create one disposable demo while onboarding begins."""
    return await service.create()


@router.get("/{session_id}", response_model=DemoSessionState)
async def get_demo_session(
    session_id: str, service: DemoServiceDependency
) -> DemoSessionState:
    """Return current provisioning and readiness state."""
    try:
        return await service.get(session_id)
    except DemoNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error


@router.post("/{session_id}/offer", response_model=VoiceAnswer)
async def answer_voice_offer(
    session_id: str, request: Request, service: DemoServiceDependency
) -> VoiceAnswer:
    """Relay browser SDP and attach the server-side voice tool loop."""
    try:
        sdp_offer = (await request.body()).decode()
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected a UTF-8 SDP offer",
        ) from None
    if not sdp_offer.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected an SDP offer",
        )
    try:
        return await service.answer_offer(session_id, sdp_offer)
    except DemoNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    except DemoConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except ProviderConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The voice connection could not be started",
        ) from error


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_demo_session(
    session_id: str, service: DemoServiceDependency
) -> Response:
    """Idempotently delete a demo and its Daytona sandbox."""
    await service.delete(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
