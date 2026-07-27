"""
Q&A endpoint — ask a question, get a grounded answer with source citations.

POST /ask
"""
import logging

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..models import User
from ..schemas import AskRequest, AskResponse
from ..services.qa_service import answer_question

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ask", tags=["qa"])


@router.post("", response_model=AskResponse)
async def ask(
    body: AskRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Answer a question from indexed YouTube transcript content.

    - Searches all indexed channels by default.
    - Pass `channel_id` to restrict the search to a single channel.
    - Answers are grounded exclusively in transcript text — the model is
      instructed not to hallucinate beyond what the videos actually say.
    - Each answer includes source citations with video title, timestamp,
      and a direct YouTube deep-link.
    """
    logger.info("Q&A request from user %d: %r", current_user.id, body.question[:80])
    return await answer_question(
        question=body.question,
        channel_id=body.channel_id,
    )
