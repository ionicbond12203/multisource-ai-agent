"""POST /chat: answers a question from the selected files."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from api.providers import ProviderError, ProviderRateLimited
from api.schemas import AskRequest, AskResponse
from api.services import Services, get_services

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model_exclude_none=True)
def chat(request: AskRequest, services: Annotated[Services, Depends(get_services)]) -> AskResponse:
    try:
        return services.agent.ask(request)
    except ProviderRateLimited as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(error)) from None
    except ProviderError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from None
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The assistant couldn't answer right now. Try again."
        ) from None
