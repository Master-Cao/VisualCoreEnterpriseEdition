#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VisionCorePro 应用入口（最小可运行骨架）
职责：
- 加载配置
- 调用 bootstrap 组装应用
- 启动/停止生命周期
"""

from .bootstrap import build_app


def main():
    app = build_app()
    app.run()


if __name__ == "__main__":
    main()
