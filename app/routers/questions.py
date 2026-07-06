from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.models.schemas import GenerateQuestionsRequest, GenerateQuestionsResponse
from app.services.openai_service import OpenAIService

router = APIRouter(prefix='/api/v1/questions', tags=['questions'])


def get_openai_service(settings: Settings = Depends(get_settings)) -> OpenAIService:
    return OpenAIService(settings)


@router.post('/generate', response_model=GenerateQuestionsResponse)
def generate_questions(
    payload: GenerateQuestionsRequest,
    service: OpenAIService = Depends(get_openai_service),
) -> GenerateQuestionsResponse:
    return service.generate_questions(payload)
