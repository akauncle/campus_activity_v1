"""活动业务蓝图（★ 活动业务核心）。

覆盖需求 FR-2 ~ FR-11：浏览列表/详情、发布、报名/取消报名、
查看报名名单、结束/取消活动。视图实现见 app/activities/views.py。
"""
from flask import Blueprint

bp = Blueprint("activities", __name__)

from app.activities import views  # noqa: E402,F401
