"""账号业务蓝图（注册/登录/登出 + 权限装饰器）。

⚠ 成员1 用户模块占位：本目录为实现 V1.0 业务闭环而按约定实现的
标准注册/登录。成员1 代码到位后，按 docs/03-软件设计.md §7 对接点替换。
"""
from flask import Blueprint

bp = Blueprint("auth", __name__)

# 延迟导入避免循环依赖
from app.auth import decorators, views  # noqa: E402,F401
