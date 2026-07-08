import json
import logging
from typing import Any

from fastapi import status
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.prompts import EXAM_QA_INSTRUCTIONS, MOTIVATION_INSTRUCTIONS, QUESTION_EXPLANATION_INSTRUCTIONS,QUESTION_GENERATOR_INSTRUCTIONS
from app.models.schemas import ChatResponse, ExamChatRequest, GenerateQuestionsRequest, GenerateQuestionsResponse, MotivationChatRequest, QuestionExplanationRequest
from app.services.safety import contains_prompt_injection

logger = logging.getLogger(__name__)

QUESTION_SET_JSON_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'properties': {
        'questions': {
            'type': 'array',
            'minItems': 1,
            'maxItems': 10,
            'items': {
                'type': 'object',
                'properties': {
                    'question': {'type': 'string'},
                    'choices': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'maxItems': 5,
                    },
                    'answer': {'type': 'string'},
                    'explanation': {'type': 'string'},
                    'era': {'type': 'string'},
                    'topic': {'type': 'string'},
                    'difficulty': {'type': 'string', 'enum': ['basic', 'intermediate', 'advanced']},
                    'exam_tip': {'type': 'string'},
                },
                'required': [
                    'question',
                    'choices',
                    'answer',
                    'explanation',
                    'era',
                    'topic',
                    'difficulty',
                    'exam_tip',
                ],
                'additionalProperties': False,
            },
        }
    },
    'required': ['questions'],
    'additionalProperties': False,
}


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: OpenAI | None = None
        if settings.openai_api_key is not None:
            self.client = OpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                timeout=settings.openai_timeout_seconds,
                max_retries=1,
            )

    def _client(self) -> OpenAI:
        if self.client is None:
            raise AppError('OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.', status.HTTP_500_INTERNAL_SERVER_ERROR)
        return self.client

    def generate_questions(self, request: GenerateQuestionsRequest) -> GenerateQuestionsResponse:
        user_prompt = (
            f'주제: {request.topic}\n'
            f'난이도: {request.difficulty.value}\n'
            f'문제 유형: {request.question_type.value}\n'
            f'문항 수: {request.count}\n'
            f'해설 포함: {request.include_explanation}\n\n'
            '요구사항:\n'
            '- multiple_choice는 choices 4개와 정답 1개를 제공한다.\n'
            '- ox는 choices를 ["O", "X"]로 제공한다.\n'
            '- short_answer는 choices를 빈 배열로 제공한다.\n'
            '- answer는 choices 중 하나이거나 단답형 정답이어야 한다.\n'
            '- explanation에는 왜 정답인지와 오답 포인트를 간단히 포함한다.\n'
            '- exam_tip에는 실제 시험 풀이 팁을 한 문장으로 작성한다.'
        )

        response_text = self._call_openai_json(
            instructions=QUESTION_GENERATOR_INSTRUCTIONS,
            user_prompt=user_prompt,
            schema_name='korean_history_question_set',
            json_schema=QUESTION_SET_JSON_SCHEMA,
        )

        try:
            data = json.loads(response_text)
            parsed = GenerateQuestionsResponse.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning('Model response validation failed: %s', exc)
            raise AppError('AI 응답 형식 검증에 실패했습니다. 다시 시도해 주세요.', status.HTTP_502_BAD_GATEWAY) from exc

        if len(parsed.questions) != request.count:
            logger.info('Requested %s questions, received %s questions', request.count, len(parsed.questions))

        return parsed

    def answer_exam_question(self, request: ExamChatRequest) -> ChatResponse:
        if contains_prompt_injection(request.message):
            return ChatResponse(answer='내부 지침이나 API 키는 공개할 수 없습니다. 대신 한국사능력검정시험 학습 질문으로 답변을 도와드리겠습니다.')

        prompt = (
            f'사용자 질문: {request.message}\n\n'
            '답변 형식:\n'
            '1) 핵심 답변\n'
            '2) 시험에 자주 나오는 포인트\n'
            '3) 암기 팁 또는 주의할 오답'
        )
        text = self._call_openai_text(EXAM_QA_INSTRUCTIONS, prompt)
        return ChatResponse(answer=text)

    def motivate(self, request: MotivationChatRequest) -> ChatResponse:
        if contains_prompt_injection(request.message):
            return ChatResponse(answer='그 요청은 도와드릴 수 없습니다. 오늘 공부할 한국사 한 단원만 정해서 20분 집중해 보는 건 어떨까요?')

        prompt = (
            f'사용자 메시지: {request.message}\n\n'
            '답변은 따뜻하지만 과장하지 말고, 바로 실천할 수 있는 행동을 포함해 주세요.'
        )
        text = self._call_openai_text(MOTIVATION_INSTRUCTIONS, prompt)
        return ChatResponse(answer=text)

    def _call_openai_text(self, instructions: str, user_prompt: str) -> str:
        try:
            response = self._client().responses.create(
                model=self.settings.openai_model,
                instructions=instructions,
                input=user_prompt,
                max_output_tokens=self.settings.openai_max_output_tokens,
            )
            output_text = response.output_text.strip()
        except AuthenticationError as exc:
            raise AppError('OpenAI API 키 인증에 실패했습니다.', status.HTTP_502_BAD_GATEWAY) from exc
        except RateLimitError as exc:
            raise AppError('OpenAI API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.', status.HTTP_429_TOO_MANY_REQUESTS) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise AppError('OpenAI API 연결이 지연되거나 실패했습니다.', status.HTTP_504_GATEWAY_TIMEOUT) from exc
        except APIError as exc:
            logger.warning('OpenAI API error: %s', exc)
            raise AppError('OpenAI API 처리 중 오류가 발생했습니다.', status.HTTP_502_BAD_GATEWAY) from exc

        if not output_text:
            raise AppError('AI 응답이 비어 있습니다. 다시 시도해 주세요.', status.HTTP_502_BAD_GATEWAY)
        return output_text

    def _call_openai_json(
        self,
        *,
        instructions: str,
        user_prompt: str,
        schema_name: str,
        json_schema: dict[str, Any],
    ) -> str:
        try:
            response = self._client().responses.create(
                model=self.settings.openai_model,
                instructions=instructions,
                input=user_prompt,
                text={
                    'format': {
                        'type': 'json_schema',
                        'name': schema_name,
                        'schema': json_schema,
                        'strict': True,
                    }
                },
                max_output_tokens=self.settings.openai_max_output_tokens,
            )
            output_text = response.output_text.strip()
        except AuthenticationError as exc:
            raise AppError('OpenAI API 키 인증에 실패했습니다.', status.HTTP_502_BAD_GATEWAY) from exc
        except RateLimitError as exc:
            raise AppError('OpenAI API 요청 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.', status.HTTP_429_TOO_MANY_REQUESTS) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise AppError('OpenAI API 연결이 지연되거나 실패했습니다.', status.HTTP_504_GATEWAY_TIMEOUT) from exc
        except APIError as exc:
            logger.warning('OpenAI API error: %s', exc)
            raise AppError('OpenAI API 처리 중 오류가 발생했습니다.', status.HTTP_502_BAD_GATEWAY) from exc

        if not output_text:
            raise AppError('AI 응답이 비어 있습니다. 다시 시도해 주세요.', status.HTTP_502_BAD_GATEWAY)
        return output_text

        
    def explain_question(self, request: QuestionExplanationRequest) -> ChatResponse:
        options_text = '\n'.join(
            [f'{option.optionNo}. {option.optionContent}' for option in request.options]
        )

        selected_text = f'{request.selectedOptionId}번' if request.selectedOptionId is not None else '선택 답안 없음'

        prompt = (
            f'[시대]\n{request.era or "미분류"}\n\n'
            f'[분류]\n{request.category or "미분류"}\n\n'
            f'[자료]\n{request.passage or "자료 없음"}\n\n'
            f'[문제]\n{request.questionContent}\n\n'
            f'[보기]\n{options_text}\n\n'
            f'[사용자 선택]\n{selected_text}\n\n'
            f'[정답]\n{request.correctOptionId}번'
        )

        text = self._call_openai_text(QUESTION_EXPLANATION_INSTRUCTIONS, prompt)
        return ChatResponse(answer=text)
