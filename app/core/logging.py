import logging
import re

_SECRET_PATTERNS = [
    re.compile(r'(sk-[A-Za-z0-9_\-]{10,})'),
    re.compile(r'(?i)(api[_-]?key\s*[=:]\s*)([^\s]+)'),
    re.compile(r'(?i)(authorization\s*:\s*bearer\s+)([^\s]+)'),
]


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for pattern in _SECRET_PATTERNS:
            if pattern.groups >= 2:
                message = pattern.sub(r'\1[REDACTED]', message)
            else:
                message = pattern.sub('[REDACTED]', message)
        return message


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        RedactingFormatter('%(asctime)s %(levelname)s %(name)s - %(message)s')
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
