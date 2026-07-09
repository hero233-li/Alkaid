import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    reserved = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in record.__dict__.items()
                if key not in self.reserved and self._is_json_value(value)
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)

    @staticmethod
    def _is_json_value(value: object) -> bool:
        return value is None or isinstance(value, (str, int, float, bool, list, dict))
