import logging
import json
import os

from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from src.a2a_server.config.settings import settings

REQUEST_ID_CTX = ContextVar("x-request-id", default="not-informed")

class JsonFormatter(logging.Formatter):
    def __init__(self, component: str, max_msg_length: int = None):
        super().__init__()
        self.component = component
        self.max_msg_length = max_msg_length

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()

        if self.max_msg_length and len(message) > self.max_msg_length:
            message = message[: self.max_msg_length] + "..."

        log_entry = {
            "level": record.levelname.lower(),
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "app_name": settings.APP_NAME,
            "x-request-id":  REQUEST_ID_CTX.get(),
            "component": record.name,
            "message": message,
        }

        return json.dumps(log_entry)
        
def setup_logger(LOG_LEVEL: str,
                 APP_NAME: str,
                 OTEL_STDOUT_LOG_GROUP: bool,
                 LOG_GROUP: str) -> None:

    root_logger  = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    handler = logging.StreamHandler()
    formatter = JsonFormatter(component=APP_NAME, max_msg_length=500)
    handler.setFormatter(formatter)

    root_logger .handlers.clear()
    root_logger .addHandler(handler)

    # File logging if OTEL_LOGS is enabled
    if OTEL_STDOUT_LOG_GROUP == True:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(LOG_GROUP), exist_ok=True) 
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        LOG_GROUP = os.path.join(BASE_DIR,LOG_GROUP)

        # File logging disabled for now
        MAX_BYTES = 10 * 1024 # 1 MB
        BACKUP_COUNT = 0    
        file_handler = RotatingFileHandler(
            LOG_GROUP,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        print(f"File logging enabled. Logs are being written to: {LOG_GROUP}")
    else:
        print("File logging is disabled. OTEL_STDOUT_LOG_GROUP is set to False")