import pytest
from pydantic import ValidationError

from app.models.schemas import ExamChatRequest, GenerateQuestionsRequest


def test_generate_questions_rejects_too_many_questions() -> None:
    with pytest.raises(ValidationError):
        GenerateQuestionsRequest(topic='삼국시대', count=11)


def test_generate_questions_normalizes_topic() -> None:
    payload = GenerateQuestionsRequest(topic='  고려   정치  ', count=3)
    assert payload.topic == '고려 정치'


def test_exam_chat_rejects_empty_message() -> None:
    with pytest.raises(Exception):
        ExamChatRequest(message='   ')
