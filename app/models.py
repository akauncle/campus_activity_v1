"""数据访问层：集中全部表结构与 SQL。

设计约定（见 docs/03-软件设计.md §3）：
- 仅依赖标准库 sqlite3，建表 DDL 与设计文档逐字一致，可互相核对；
- 三张表与全部 SQL 集中在本文件，视图层不出现散落 SQL；
- 时间统一存本机时间字符串 'YYYY-MM-DD HH:MM'，字典序即时间序。
"""
import sqlite3
from datetime import datetime

from flask import current_app, g

# ---------------------------------------------------------------- 表结构
# 注意：DDL 与 docs/03-软件设计.md §3 保持一致，改动需同步文档并登记调整记录

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('student', 'teacher')),
    nickname      TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS activities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    location        TEXT NOT NULL,
    teacher_id      INTEGER NOT NULL REFERENCES users(id),
    start_time      TEXT NOT NULL,             -- 'YYYY-MM-DD HH:MM'
    signup_deadline TEXT NOT NULL,             -- 报名截止，须早于 start_time
    capacity        INTEGER NOT NULL DEFAULT 0 CHECK (capacity >= 0),  -- 0=不限
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'cancelled', 'finished')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS registrations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id INTEGER NOT NULL REFERENCES activities(id),
    student_id  INTEGER NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (activity_id, student_id)           -- 防重复报名：数据库层兜底
);

CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_time);
CREATE INDEX IF NOT EXISTS idx_reg_activity ON registrations(activity_id);
CREATE INDEX IF NOT EXISTS idx_reg_student  ON registrations(student_id);
"""

# 活动生命周期状态（只存事件状态，展示状态由时间推导，见设计决策 2）
STATUS_ACTIVE = "active"        # 正常（报名通道是否开放看时间）
STATUS_CANCELLED = "cancelled"  # 教师取消
STATUS_FINISHED = "finished"    # 教师结束

# ---------------------------------------------------------------- 时间工具

TIME_FMT = "%Y-%m-%d %H:%M"


def now_str():
    """当前时间字符串，用于与库中时间直接比较。"""
    return datetime.now().strftime(TIME_FMT)


def parse_time(s):
    """解析库中时间；非法返回 None。"""
    try:
        return datetime.strptime(s, TIME_FMT)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- 连接管理

def get_db():
    """每个请求一个连接，挂到 flask.g 上，请求结束由 teardown 关闭。"""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    """应用启动时建库建表（幂等）。"""
    import os

    db_path = app.config["DATABASE"]
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- users
# users 表字段：id / username(唯一) / password_hash / role / nickname / created_at

def create_user(username, password_hash, role, nickname):
    """新建用户，返回新用户 id；用户名重复抛出 sqlite3.IntegrityError，
    由调用方转为友好提示。"""
    db = get_db()
    cur = db.execute(
        "INSERT INTO users (username, password_hash, role, nickname) VALUES (?, ?, ?, ?)",
        (username, password_hash, role, nickname),
    )
    db.commit()
    return cur.lastrowid


def get_user(user_id):
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_username(username):
    return get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


# ---------------------------------------------------------------- activities

def create_activity(title, description, location, teacher_id, start_time,
                    signup_deadline, capacity=0):
    db = get_db()
    cur = db.execute(
        """INSERT INTO activities
           (title, description, location, teacher_id, start_time, signup_deadline, capacity)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (title, description, location, teacher_id, start_time, signup_deadline, capacity),
    )
    db.commit()
    return cur.lastrowid


def get_activity(activity_id):
    return get_db().execute(
        "SELECT * FROM activities WHERE id = ?", (activity_id,)
    ).fetchone()


def list_activities():
    """全部活动，按活动开始时间升序。"""
    return get_db().execute(
        "SELECT * FROM activities ORDER BY start_time"
    ).fetchall()


# 列表/详情通用查询列：带发布教师昵称与已报名人数
_STATS_SELECT = """
    SELECT a.*, u.nickname AS teacher_name,
           COUNT(r.id) AS reg_count
    FROM activities a
    JOIN users u ON u.id = a.teacher_id
    LEFT JOIN registrations r ON r.activity_id = a.id
"""


def list_activities_with_stats():
    """全部活动 + 教师昵称 + 报名人数，按活动开始时间升序（FR-2）。"""
    return get_db().execute(
        _STATS_SELECT + " GROUP BY a.id ORDER BY a.start_time"
    ).fetchall()


def get_activity_with_stats(activity_id):
    """单个活动 + 教师昵称 + 报名人数；不存在返回 None。"""
    return get_db().execute(
        _STATS_SELECT + " WHERE a.id = ? GROUP BY a.id", (activity_id,)
    ).fetchone()


def list_activities_by_teacher(teacher_id):
    return get_db().execute(
        "SELECT * FROM activities WHERE teacher_id = ? ORDER BY start_time DESC",
        (teacher_id,),
    ).fetchall()


def list_activities_by_teacher_with_stats(teacher_id):
    """某教师发布的活动 + 报名人数（FR-11）。"""
    return get_db().execute(
        _STATS_SELECT + " WHERE a.teacher_id = ? GROUP BY a.id "
                        "ORDER BY a.start_time DESC",
        (teacher_id,),
    ).fetchall()


def set_activity_status(activity_id, status):
    db = get_db()
    db.execute("UPDATE activities SET status = ? WHERE id = ?", (status, activity_id))
    db.commit()


def count_registrations(activity_id):
    row = get_db().execute(
        "SELECT COUNT(*) AS n FROM registrations WHERE activity_id = ?",
        (activity_id,),
    ).fetchone()
    return row["n"]


def registrations_full(activity_id, capacity):
    """名额是否已满：capacity<=0 视为不限，永不满。"""
    if capacity <= 0:
        return False
    return count_registrations(activity_id) >= capacity


# ---------------------------------------------------------------- registrations

def add_registration(activity_id, student_id):
    """写入报名记录；重复报名抛出 sqlite3.IntegrityError（UNIQUE 兜底）。"""
    db = get_db()
    db.execute(
        "INSERT INTO registrations (activity_id, student_id) VALUES (?, ?)",
        (activity_id, student_id),
    )
    db.commit()


def has_registration(activity_id, student_id):
    row = get_db().execute(
        "SELECT 1 FROM registrations WHERE activity_id = ? AND student_id = ?",
        (activity_id, student_id),
    ).fetchone()
    return row is not None


def remove_registration(activity_id, student_id):
    db = get_db()
    db.execute(
        "DELETE FROM registrations WHERE activity_id = ? AND student_id = ?",
        (activity_id, student_id),
    )
    db.commit()


def list_signed_activity_ids(student_id):
    """某学生已报名的活动 id 集合（列表页展示"已报名"标识）。"""
    rows = get_db().execute(
        "SELECT activity_id FROM registrations WHERE student_id = ?",
        (student_id,),
    ).fetchall()
    return {r["activity_id"] for r in rows}


def list_registrants(activity_id):
    """报名名单：学生昵称/账号/报名时间，按报名先后。"""
    return get_db().execute(
        """SELECT u.nickname, u.username, r.created_at AS signed_at
           FROM registrations r JOIN users u ON u.id = r.student_id
           WHERE r.activity_id = ?
           ORDER BY r.id""",
        (activity_id,),
    ).fetchall()
