from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.safety import normalize_user_text


class Difficulty(str, Enum):
    basic = 'basic'
    intermediate = 'intermediate'
    advanced = 'advanced'


class QuestionType(str, Enum):
    multiple_choice = 'multiple_choice'
    short_answer = 'short_answer'
    ox = 'ox'


class GenerateQuestionsRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    topic: str = Field(..., min_length=2, max_length=50, description='예: 삼국시대, 고려 정치, 조선 후기')
    difficulty: Difficulty = Field(default=Difficulty.intermediate)
    question_type: QuestionType = Field(default=QuestionType.multiple_choice)
    count: int = Field(default=5, ge=1, le=10)
    include_explanation: bool = Field(default=True)

    @field_validator('topic')
    @classmethod
    def validate_topic(cls, value: str) -> str:
        return normalize_user_text(value, max_length=50)


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')

    question: str = Field(..., min_length=5, max_length=600)
    choices: list[str] = Field(default_factory=list, max_length=5)
    answer: str = Field(..., min_length=1, max_length=200)
    explanation: str = Field(..., min_length=1, max_length=1000)
    era: str = Field(..., min_length=1, max_length=80)
    topic: str = Field(..., min_length=1, max_length=80)
    difficulty: Difficulty
    exam_tip: str = Field(..., min_length=1, max_length=300)


class GenerateQuestionsResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    questions: list[GeneratedQuestion] = Field(..., min_length=1, max_length=10)


class ExamChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    message: str = Field(..., min_length=2, max_length=1500)

    @field_validator('message')
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_user_text(value, max_length=1500)


class MotivationChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    message: str = Field(..., min_length=1, max_length=800)

    @field_validator('message')
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_user_text(value, max_length=800)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    answer: str = Field(..., min_length=1, max_length=3000)
