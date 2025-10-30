#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VisionCorePro 应用入口
职责：
- 加载配置
- 调用 bootstrap 组装应用
- 启动/停止生命周期
"""

try:
    from .bootstrap import build_app  # 包内运行（python -m app.main）
except ImportError:
    # 直接脚本方式运行时，补充包路径，兼容调试器默认行为
    import os
    import sys

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)

    from app.bootstrap import build_app


def main():
    app = build_app()
    app.run()


if __name__ == "__main__":
    main()
