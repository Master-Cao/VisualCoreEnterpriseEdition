from enum import Enum


class MessageType(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    DEBUG = "debug"
    CRITICAL = "critical"
    SUCCESS = "success"
    FAILURE = "failure"


class VisionCoreCommands(Enum):
    RESTART = "restart"
    GET_CONFIG = "get_config"
    SAVE_CONFIG = "save_config"
    GET_IMAGE = "get_image"
    GET_CALIBRAT_IMAGE = "get_calibrat_image"
    SFTP_TEST = "sftp_test"
    GET_SYSTEM_STATUS = "get_system_status"
    MODEL_TEST = "model_test"
    COORDINATE_CALIBRATION = "coordinate_calibration"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

    def __hash__(self):
        return hash(self.value)

    @classmethod
    def values(cls):
        return [c.value for c in cls]
