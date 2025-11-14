#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VisionCorePro 应用入口
职责：
- 加载配置
- 调用 bootstrap 组装应用
- 启动/停止生命周期
"""

import os
import sys

if __package__ in (None, ""):
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)
    from app.bootstrap import build_app
else:
    from .bootstrap import build_app  # type: ignore


def main():
    app = build_app()
    app.run()

# [X:363.30, Y:-110.74, Z:-85.00, A:0.00]
if __name__ == "__main__":
    main()
