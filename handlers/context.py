# -*- coding: utf-8 -*-

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CommandContext:
    config: dict
    camera: Optional[Any]
    detector: Optional[Any]
    sftp: Optional[Any]
    monitor: Optional[Any]
    logger: Optional[Any]
    project_root: str
    initializer: Optional[Any] = None
    
    # 遮挡检测状态：剩余需要忽略的检测次数
    # 当TCP间隔超过阈值时，设置此值为N，接下来的N次检测都返回遮挡标志
    occlusion_ignore_remaining: int = field(default=0, init=False)


