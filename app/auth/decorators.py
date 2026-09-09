"""权限装饰器：登录/角色校验集中在登录会话约定上。

对接约定（成员1 需保持一致）：登录成功后写入
    session['user_id']  用户 id
    session['role']     'student' | 'teacher'
若队友实现不同，仅需调整本文件。
"""
from functools import wraps

from flask import abort, flash, redirect, session, url_for


def current_user_id():
    return session.get("user_id")


def current_role():
    return session.get("role")


def is_logged_in():
    return current_user_id() is not None


def login_required(view):
    """未登录 → 提示并引导到登录页。"""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_logged_in():
            flash("请先登录后再操作", "warning")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def _role_required(role):
    """登录且身份匹配，否则 403。"""

    def deco(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_role() != role:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return deco


teacher_required = _role_required("teacher")  # 仅教师
student_required = _role_required("student")  # 仅学生
