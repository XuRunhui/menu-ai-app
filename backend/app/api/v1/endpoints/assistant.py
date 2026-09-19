"""AI dining assistant endpoint: one turn of conversation per request."""

import logging

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from app.core.rate_limit import enforce_demo_limits
from app.models.assistant import AssistantRequest, AssistantResponse
from app.services.assistant.agent import respond

router = APIRouter()
logger = logging.getLogger(__name__)


# Registered with and without the trailing slash so proxied requests never hit a redirect
# whose Location points at the internal backend address.
@router.post("/chat", response_model=AssistantResponse, dependencies=[Depends(enforce_demo_limits)])
async def chat(request: AssistantRequest) -> AssistantResponse:
    """Continue the conversation and return the reply plus the updated transcript.

    The server keeps nothing: send back the ``messages`` from the response, together with whatever
    the browser knows about where the diner is, and the next turn picks up where this one left off.

    The assistant may search Google Places, look a restaurant up in detail, or consult the local
    knowledge base while answering — ``tools_used`` says which it did. With no DeepSeek key
    configured it falls back to a scripted three-question flow that still returns real restaurants.

    Args:
        request: The transcript so far plus the diner's location context.

    Returns:
        The reply, the transcript to send next time, restaurant cards, and quick-reply chips.
    """
    return await run_in_threadpool(respond, request)
