from __future__ import annotations

import logging
import re


class SecretRedactionFilter(logging.Filter):
    patterns = [
        re.compile(r"(?i)(secret|password|token|credential|authorization|cookie)=([^\\s]+)"),
        re.compile(r"(?i)(consumer[_-]?key|consumer[_-]?secret)=([^\\s]+)"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self.patterns:
            message = pattern.sub(r"\\1=[redacted]", message)
        record.msg = message
        record.args = ()
        return True

