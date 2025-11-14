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
    # 配置管理命令
    GET_CONFIG = "get_config"
    SAVE_CONFIG = "save_config"
    
    # 相机命令
    GET_IMAGE = "get_image"
    
    # 检测命令
    MODEL_TEST = "model_test"
    CATCH = "catch"
    
    # 标定命令
    GET_CALIBRAT_IMAGE = "get_calibrat_image"
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
