"""账号业务蓝图（注册/登录/登出 + 权限装饰器）。

对应 FR-1：注册时选择身份（学生/教师）、密码单向哈希存储、登录后以会话
携带用户 id 与角色。与活动蓝图的分工见 docs/03-软件设计.md §1。
"""
from flask import Blueprint

bp = Blueprint("auth", __name__)

# 延迟导入避免循环依赖
from app.auth import decorators, views  # noqa: E402,F401
