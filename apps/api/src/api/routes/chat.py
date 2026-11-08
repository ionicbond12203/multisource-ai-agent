"""POST /chat: answers a question from the selected files."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.providers import ProviderError, ProviderRateLimited
from api.rate_limit import client_key
from api.schemas import AskRequest, AskResponse
from api.services import Services, get_services

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model_exclude_none=True)
def chat(
    request: AskRequest, http: Request, services: Annotated[Services, Depends(get_services)]
) -> AskResponse:
    services.limits.chat.check(client_key(http))
    try:
        return services.agent.ask(request)
    except ProviderRateLimited as error:
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(error), headers=headers) from None
    except ProviderError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from None
    except Exception:
        logger.exception("Chat request failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The assistant couldn't answer right now. Try again."
        ) from None
