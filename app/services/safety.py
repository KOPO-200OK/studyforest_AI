import re
import unicodedata

from app.core.exceptions import AppError

_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
_SUSPICIOUS_PROMPT_INJECTION = re.compile(
    r'(?i)(ignore\s+previous|system\s+prompt|developer\s+message|api\s*key|프롬프트\s*공개|시스템\s*지침|개발자\s*메시지)'
)


def normalize_user_text(value: str, *, max_length: int) -> str:
    value = unicodedata.normalize('NFKC', value)
    value = _CONTROL_CHARS.sub('', value)
    value = re.sub(r'\s+', ' ', value).strip()

    if not value:
        raise AppError('빈 문자열은 사용할 수 없습니다.', status_code=422)
    if len(value) > max_length:
        raise AppError(f'입력은 최대 {max_length}자까지 가능합니다.', status_code=422)
    return value


def contains_prompt_injection(value: str) -> bool:
    return bool(_SUSPICIOUS_PROMPT_INJECTION.search(value))
