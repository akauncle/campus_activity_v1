"""注册 / 登录 / 登出（FR-1）。

密码使用 werkzeug 单向哈希存储，不落明文；登录成功后写入会话约定键
session['user_id'] 与 session['role']，供 app/auth/decorators.py 的
权限装饰器与全部视图读取。
"""
import sqlite3

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app import models
from app.auth import bp
from app.auth.decorators import is_logged_in

ROLE_LABELS = {"student": "学生", "teacher": "教师"}


@bp.route("/register", methods=("GET", "POST"))
def register():
    """注册：选择身份（学生/教师），密码哈希存储。"""
    if is_logged_in():
        return redirect(url_for("activities.index"))

    errors = []
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        nickname = (request.form.get("nickname") or "").strip() or username
        password = request.form.get("password") or ""
        password2 = request.form.get("password2") or ""
        role = request.form.get("role")

        if not username or not password:
            errors.append("用户名与密码不能为空")
        elif len(password) < 6:
            errors.append("密码至少 6 位")
        elif password != password2:
            errors.append("两次输入的密码不一致")
        elif role not in ("student", "teacher"):
            errors.append("请选择身份：学生或教师")

        if not errors:
            try:
                models.create_user(
                    username,
                    generate_password_hash(password),
                    role,
                    nickname,
                )
            except sqlite3.IntegrityError:
                errors.append(f"用户名「{username}」已被注册")
            else:
                flash(f"注册成功，请登录（身份：{ROLE_LABELS[role]}）", "success")
                return redirect(url_for("auth.login"))

    return render_template("auth/register.html", errors=errors,
                           form=request.form, role_labels=ROLE_LABELS)


@bp.route("/login", methods=("GET", "POST"))
def login():
    if is_logged_in():
        return redirect(url_for("activities.index"))

    errors = []
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = models.get_user_by_username(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            errors.append("用户名或密码错误")
        else:
            session.clear()
            session["user_id"] = user["id"]          # 会话约定：用户 id
            session["role"] = user["role"]           # 会话约定：身份角色
            flash(f"欢迎回来，{user['nickname'] or user['username']}"
                  f"（{ROLE_LABELS[user['role']]}）", "success")
            return redirect(url_for("activities.index"))

    return render_template("auth/login.html", errors=errors, form=request.form)


@bp.route("/logout", methods=("POST",))
def logout():
    session.clear()
    flash("已退出登录", "info")
    return redirect(url_for("activities.index"))
