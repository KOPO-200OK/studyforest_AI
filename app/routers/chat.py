from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.models.schemas import ChatResponse, ExamChatRequest, MotivationChatRequest
from app.services.openai_service import OpenAIService

router = APIRouter(prefix='/api/v1/chat', tags=['chat'])


def get_openai_service(settings: Settings = Depends(get_settings)) -> OpenAIService:
    return OpenAIService(settings)


@router.post('/exam', response_model=ChatResponse)
def exam_chat(
    payload: ExamChatRequest,
    service: OpenAIService = Depends(get_openai_service),
) -> ChatResponse:
    return service.answer_exam_question(payload)


@router.post('/motivation', response_model=ChatResponse)
def motivation_chat(
    payload: MotivationChatRequest,
    service: OpenAIService = Depends(get_openai_service),
) -> ChatResponse:
    return service.motivate(payload)
