from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from ..enums.commands import MessageType


@dataclass
class MQTTResponse:
    command: str
    component: str
    messageType: MessageType
    message: str
    data: Dict[str, Any]
    timestamp: float = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "component": self.component,
            "messageType": self.messageType.value if hasattr(self.messageType, "value") else str(self.messageType),
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp or datetime.now().timestamp(),
        }
