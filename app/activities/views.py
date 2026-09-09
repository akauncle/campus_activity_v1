"""活动蓝图视图：暂为骨架占位，列表/详情等路由将在下一步实现。"""
from flask import render_template

from app.activities import bp


@bp.route("/activities")
def index():
    return render_template("activities/index.html")
