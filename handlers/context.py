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
    gpio: Optional[Any] = None


