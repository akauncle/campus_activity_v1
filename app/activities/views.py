"""活动蓝图视图（★ 成员2 活动业务模块核心）。

路由与需求对应见 docs/03-软件设计.md §5。所有状态/时间/归属校验都在
本文件的服务端完成，页面只是展示入口。
"""
from datetime import datetime

from flask import abort, flash, redirect, render_template, request, session, url_for

from app import models
from app.activities import bp
from app.auth.decorators import teacher_required

# ------------------------------------------------------------- 派生展示状态
# 设计决策 2（docs/03 §2.2）：数据库只存生命周期事件状态，这里按时间推导
# 展示状态与报名通道。keys 同时作为样式类名后缀。

# 展示状态：key（同时作样式类名）→ (中文标签, 说明)
STATUS_INFO = {
    "open":     ("报名中",   "报名通道开放"),
    "closed":   ("报名截止", "已过报名截止时间"),
    "ongoing":  ("进行中",   "活动开始，等待教师结束"),
    "finished": ("已结束",   "教师标记结束"),
    "cancelled": ("已取消",  "教师取消活动"),
}


def disp_status_key(activity, now=None):
    """按『生命周期状态 + 时间』推导展示状态 key。"""
    now = now or models.now_str()
    if activity["status"] == models.STATUS_CANCELLED:
        return "cancelled"
    if activity["status"] == models.STATUS_FINISHED:
        return "finished"
    if now <= activity["signup_deadline"]:
        return "open"
    if now <= activity["start_time"]:
        return "closed"
    return "ongoing"


def status_view(activity, now=None):
    """给模板用的展示状态 dict：{key, label, note}。"""
    key = disp_status_key(activity, now)
    label, note = STATUS_INFO[key]
    return {"key": key, "label": label, "note": note}


def signup_open(activity, now=None):
    """报名通道是否开放（FR-5 规则 ①②③④的一部分，满员在报名时单独判断）。"""
    return (
        activity["status"] == models.STATUS_ACTIVE
        and (now or models.now_str()) <= activity["signup_deadline"]
        and not models.registrations_full(activity["id"], activity["capacity"])
    )


def capacity_text(activity):
    if activity["capacity"] <= 0:
        return "不限"
    return f"{activity['capacity']} 人"


def _current_user():
    """当前登录用户行（依赖成员1对接约定的会话键，见 auth/decorators.py）。"""
    uid = session.get("user_id")
    return models.get_user(uid) if uid else None


# ------------------------------------------------------------- 浏览（FR-2/FR-3，公开）

@bp.route("/activities")
def index():
    """活动列表：全部可见，派生状态徽标 + 名额，按开始时间排序（FR-2）。"""
    activities = models.list_activities_with_stats()
    now = models.now_str()
    return render_template(
        "activities/index.html",
        activities=activities,
        statuses={a["id"]: status_view(a, now) for a in activities},
        capacity_text=capacity_text,
    )


@bp.route("/activities/<int:activity_id>")
def detail(activity_id):
    """活动详情：完整信息 + 按身份渲染操作区（FR-3）。"""
    activity = models.get_activity_with_stats(activity_id)
    if activity is None:
        abort(404)
    now = models.now_str()
    user = _current_user()
    ctx = {
        "activity": activity,
        "status": status_view(activity, now),
        "capacity_text": capacity_text,
        "can_signup": signup_open(activity, now),   # 通道开放但可能已满员
        "is_owner": bool(user and user["id"] == activity["teacher_id"]),
        "signed_up": bool(user
                          and models.has_registration(activity["id"], user["id"])),
    }
    return render_template("activities/detail.html", **ctx)


# ------------------------------------------------------------- 发布活动（FR-4，教师）

def _normalize_time(raw):
    """datetime-local 表单值 'YYYY-MM-DDTHH:MM' → 库格式 'YYYY-MM-DD HH:MM'。"""
    if not raw:
        return ""
    return raw.strip().replace("T", " ")


def _validate_activity_form(form, now):
    """发布表单校验；返回 (errors, values)，values 为可入库的字段 dict。"""
    errors = []
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip()
    location = (form.get("location") or "").strip()
    start_raw = _normalize_time(form.get("start_time"))
    deadline_raw = _normalize_time(form.get("signup_deadline"))
    capacity_raw = (form.get("capacity") or "").strip()

    if not title:
        errors.append("请填写活动主题")
    if not description:
        errors.append("请填写活动介绍")
    if not location:
        errors.append("请填写活动地点")

    def valid_time(s):
        try:
            return datetime.strptime(s, models.TIME_FMT)
        except ValueError:
            return None

    start_dt, deadline_dt = valid_time(start_raw), valid_time(deadline_raw)
    if start_dt is None:
        errors.append("活动开始时间格式不正确")
    if deadline_dt is None:
        errors.append("报名截止时间格式不正确")
    if start_dt and start_dt <= datetime.now():
        errors.append("活动开始时间必须晚于当前时间")
    if deadline_dt and start_dt and deadline_dt >= start_dt:
        errors.append("报名截止时间必须早于活动开始时间")
    if deadline_dt and deadline_dt <= datetime.now():
        errors.append("报名截止时间必须晚于当前时间（发布后应能报名）")

    capacity = 0
    if capacity_raw:
        try:
            capacity = int(capacity_raw)
            if capacity < 0:
                raise ValueError
        except ValueError:
            errors.append("人数上限须为非负整数（留空或 0 表示不限）")

    if errors:
        return errors, None
    return [], {
        "title": title, "description": description, "location": location,
        "start_time": start_raw, "signup_deadline": deadline_raw,
        "capacity": capacity,
    }


@bp.route("/activities/new", methods=("GET", "POST"))
@teacher_required
def new_activity():
    """发布活动：表单 + 服务端时间/容量校验（FR-4）。"""
    values = None
    if request.method == "POST":
        errors, values = _validate_activity_form(request.form, models.now_str())
        if not errors:
            activity_id = models.create_activity(
                title=values["title"], description=values["description"],
                location=values["location"], start_time=values["start_time"],
                signup_deadline=values["signup_deadline"],
                capacity=values["capacity"], teacher_id=session["user_id"],
            )
            flash(f"活动「{values['title']}」发布成功", "success")
            return redirect(url_for("activities.detail", activity_id=activity_id))
        return render_template(
            "activities/new.html", errors=errors,
            form={**request.form, "capacity": values["capacity"] if values else ""},
        )
    return render_template("activities/new.html", errors=[], form={})


# ------------------------------------------------------------- 我发布的活动（FR-11，教师）

@bp.route("/activities/mine")
@teacher_required
def mine():
    """教师查看自己发布的活动与报名情况（管理入口，FR-11）。"""
    activities = models.list_activities_by_teacher_with_stats(session["user_id"])
    now = models.now_str()
    return render_template(
        "activities/mine.html",
        activities=activities,
        statuses={a["id"]: status_view(a, now) for a in activities},
        capacity_text=capacity_text,
    )
