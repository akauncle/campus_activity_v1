"""应用工厂：创建 Flask 应用、初始化数据库、注册蓝图。

模块组织（docs/03-软件设计.md §1）：
- app/models.py   数据访问层（表 DDL + SQL 集中处）
- app/auth/       账号蓝图 ⚠ 成员1 职责占位（对接点见 docs/03 §7）
- app/activities/ 活动蓝图 ★ 成员2 活动业务模块
"""
import os

from flask import Flask, redirect, render_template, session, url_for

from app import config, models

ROLE_LABELS = {"student": "学生", "teacher": "教师"}


def create_app(test_config=None):
    app = Flask(__name__)
    config.init_app_config(app)
    if test_config:                     # 测试：覆盖 DATABASE 等配置
        app.config.update(test_config)

    models.init_db(app)                 # 建库建表（幂等）
    app.teardown_appcontext(models.close_db)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.activities import bp as activities_bp   # 活动业务模块
    app.register_blueprint(activities_bp)

    @app.context_processor
    def inject_user():
        """模板全局：current_user（None 表示未登录）。"""
        uid = session.get("user_id")
        user = models.get_user(uid) if uid else None
        return dict(current_user=user, role_labels=ROLE_LABELS)

    @app.route("/")
    def home():
        return redirect(url_for("activities.index"))

    return app
