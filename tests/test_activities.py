"""活动业务模块自动化测试（unittest，零第三方测试依赖）。

运行：python -m unittest discover -s tests -v
覆盖需求：FR-1（占位冒烟）、FR-2/3、FR-4、FR-5/6、FR-8/9/10
与 02-工程意图 §5 完成判据 2 的规则分支。每用例独立临时数据库。
"""
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

from app import create_app, models
from app.activities.views import disp_status_key, status_view


def mkt(days, hours=10):
    """相对当前时间偏移的库格式时间串。"""
    return (datetime.now() + timedelta(days=days, hours=hours)
            ).strftime(models.TIME_FMT)


class ActivityTestCase(unittest.TestCase):
    """基类：每个用例一个临时库 + 基础角色数据。"""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()
        with self.app.app_context():
            self.t1 = models.create_user("t1", "h", "teacher", "王老师")
            self.t2 = models.create_user("t2", "h", "teacher", "李老师")
            self.s1 = models.create_user("s1", "h", "student", "小明")
            self.s2 = models.create_user("s2", "h", "student", "小红")

    def tearDown(self):
        os.remove(self.db_path)

    # ---- 工具 ----
    def login(self, uid, role):
        self.client.post("/logout")
        with self.client.session_transaction() as s:
            s["user_id"] = uid
            s["role"] = role

    def logout(self):
        self.client.post("/logout")

    def make_activity(self, teacher=None, capacity=0, deadline_days=3,
                      start_days=7, status=models.STATUS_ACTIVE):
        with self.app.app_context():
            aid = models.create_activity(
                title="测试活动", description="活动介绍", location="教室 A",
                teacher_id=teacher or self.t1,
                start_time=mkt(start_days), signup_deadline=mkt(deadline_days),
                capacity=capacity)
            if status != models.STATUS_ACTIVE:
                models.set_activity_status(aid, status)
        return aid

    # ================= FR-4 发布权限与校验 =================

    def test_student_cannot_publish(self):
        self.login(self.s1, "student")
        self.assertEqual(self.client.get("/activities/new").status_code, 403)
        r = self.client.post("/activities/new", data={
            "title": "x", "description": "d", "location": "l",
            "start_time": mkt(7, 14).replace(" ", "T"),
            "signup_deadline": mkt(3, 12).replace(" ", "T"),
        })
        self.assertEqual(r.status_code, 403)

    def test_anonymous_publish_redirects_login(self):
        r = self.client.get("/activities/new")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_teacher_publish_success(self):
        self.login(self.t1, "teacher")
        start, deadline = mkt(7, 14).replace(" ", "T"), mkt(3, 12).replace(" ", "T")
        r = self.client.post("/activities/new", data={
            "title": "新生见面会", "description": "欢迎", "location": "活动中心",
            "start_time": start, "signup_deadline": deadline, "capacity": "50",
        })
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            rows = models.list_activities()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["teacher_id"], self.t1)
            self.assertEqual(rows[0]["capacity"], 50)
            self.assertEqual(rows[0]["status"], models.STATUS_ACTIVE)

    def test_publish_validation_errors(self):
        self.login(self.t1, "teacher")
        start = mkt(7, 14).replace(" ", "T")
        past = mkt(-1, 14).replace(" ", "T")
        later = mkt(9, 14).replace(" ", "T")
        cases = [
            {"title": "", "description": "d", "location": "l",
             "start_time": start, "signup_deadline": later},          # 空标题
            {"title": "x", "description": "d", "location": "l",
             "start_time": start, "signup_deadline": later},          # 截止晚于开始
            {"title": "x", "description": "d", "location": "l",
             "start_time": past, "signup_deadline": past},            # 已开始
            {"title": "x", "description": "d", "location": "l",
             "start_time": start, "signup_deadline": mkt(3, 12).replace(" ", "T"),
             "capacity": "abc"},                                      # 非法容量
        ]
        for data in cases:
            r = self.client.post("/activities/new", data=data)
            self.assertEqual(r.status_code, 200)
            self.assertIn(b"flash-error", r.data, msg=data)
        with self.app.app_context():
            self.assertEqual(len(models.list_activities()), 0, "校验失败不应落库")

    # ================= FR-5 报名规则 =================

    def test_signup_success_and_duplicate_blocked(self):
        aid = self.make_activity()
        self.login(self.s1, "student")
        r = self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
        self.assertIn("报名成功", r.get_data(as_text=True))
        r = self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
        self.assertIn("请勿重复报名", r.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(models.count_registrations(aid), 1)

    def test_signup_after_deadline_blocked(self):
        aid = self.make_activity(deadline_days=-1)     # 截止已过
        self.login(self.s1, "student")
        r = self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
        self.assertIn("报名已截止", r.get_data(as_text=True))

    def test_signup_full_and_unlimited(self):
        aid = self.make_activity(capacity=1)
        self.login(self.s1, "student")
        self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
        self.login(self.s2, "student")
        r = self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
        self.assertIn("名额已满", r.get_data(as_text=True))

        aid2 = self.make_activity(capacity=0)          # 0 = 不限
        self.login(self.s1, "student")
        self.client.post(f"/activities/{aid2}/signup", follow_redirects=True)
        self.login(self.s2, "student")
        r = self.client.post(f"/activities/{aid2}/signup", follow_redirects=True)
        self.assertIn("报名成功", r.get_data(as_text=True))

    def test_signup_after_finish_or_cancel_blocked(self):
        for status in (models.STATUS_FINISHED, models.STATUS_CANCELLED):
            aid = self.make_activity(status=status)
            self.login(self.s1, "student")
            r = self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
            self.assertIn("已取消或已结束", r.get_data(as_text=True))

    def test_teacher_cannot_signup_anonymous_redirects(self):
        aid = self.make_activity()
        self.login(self.t1, "teacher")
        self.assertEqual(self.client.post(f"/activities/{aid}/signup").status_code, 403)
        self.logout()
        r = self.client.post(f"/activities/{aid}/signup")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    # ================= FR-6 取消报名 =================

    def test_unsignup_before_deadline(self):
        aid = self.make_activity()
        with self.app.app_context():
            models.add_registration(aid, self.s1)
        self.login(self.s1, "student")
        r = self.client.post(f"/activities/{aid}/unsignup", follow_redirects=True)
        self.assertIn("已取消报名", r.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(models.count_registrations(aid), 0)

    def test_unsignup_locked_after_deadline(self):
        aid = self.make_activity(deadline_days=-1)
        with self.app.app_context():
            models.add_registration(aid, self.s1)
        self.login(self.s1, "student")
        r = self.client.post(f"/activities/{aid}/unsignup", follow_redirects=True)
        self.assertIn("名单已锁定", r.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(models.count_registrations(aid), 1)   # 记录仍在

    def test_unsignup_without_signup(self):
        aid = self.make_activity()
        self.login(self.s1, "student")
        r = self.client.post(f"/activities/{aid}/unsignup", follow_redirects=True)
        self.assertIn("你尚未报名", r.get_data(as_text=True))

    # ================= FR-8/9/10 教师管理 =================

    def _seed_registration(self, aid, student_id):
        with self.app.app_context():
            models.add_registration(aid, student_id)

    def test_registrants_only_for_owner(self):
        aid = self.make_activity()
        self._seed_registration(aid, self.s1)
        # 发布教师可见名单与学生信息
        self.login(self.t1, "teacher")
        body = self.client.get(f"/activities/{aid}/registrants").get_data(as_text=True)
        self.assertIn("小明", body)
        self.assertIn("s1", body)
        # 其他教师 / 学生 403，未登录 302
        self.login(self.t2, "teacher")
        self.assertEqual(self.client.get(f"/activities/{aid}/registrants").status_code, 403)
        self.login(self.s1, "student")
        self.assertEqual(self.client.get(f"/activities/{aid}/registrants").status_code, 403)
        self.logout()
        r = self.client.get(f"/activities/{aid}/registrants")
        self.assertEqual(r.status_code, 302)

    def test_finish_and_cancel_owner_only(self):
        aid = self.make_activity()
        self.login(self.t2, "teacher")
        self.assertEqual(self.client.post(f"/activities/{aid}/finish").status_code, 403)
        self.assertEqual(self.client.post(f"/activities/{aid}/cancel").status_code, 403)
        self.login(self.s1, "student")
        self.assertEqual(self.client.post(f"/activities/{aid}/finish").status_code, 403)

    def test_finish_then_rules(self):
        aid = self.make_activity()
        self._seed_registration(aid, self.s1)
        self.login(self.t1, "teacher")
        r = self.client.post(f"/activities/{aid}/finish", follow_redirects=True)
        self.assertIn("已标记为结束", r.get_data(as_text=True))
        # 重复结束被拒
        r = self.client.post(f"/activities/{aid}/finish", follow_redirects=True)
        self.assertIn("不可执行", r.get_data(as_text=True))
        # 名单保留、报名被拒
        with self.app.app_context():
            self.assertEqual(models.get_activity(aid)["status"], models.STATUS_FINISHED)
            self.assertEqual(models.count_registrations(aid), 1)
        self.login(self.s2, "student")
        r = self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
        self.assertIn("已取消或已结束", r.get_data(as_text=True))

    def test_cancel_then_rules(self):
        aid = self.make_activity()
        self._seed_registration(aid, self.s1)
        self.login(self.t1, "teacher")
        r = self.client.post(f"/activities/{aid}/cancel", follow_redirects=True)
        self.assertIn("已取消", r.get_data(as_text=True))
        # 取消后结束被拒；报名被拒；名单保留
        r = self.client.post(f"/activities/{aid}/finish", follow_redirects=True)
        self.assertIn("不可执行", r.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(models.get_activity(aid)["status"], models.STATUS_CANCELLED)
            self.assertEqual(models.count_registrations(aid), 1)
        self.login(self.s1, "student")
        r = self.client.post(f"/activities/{aid}/signup", follow_redirects=True)
        self.assertIn("已取消或已结束", r.get_data(as_text=True))

    # ================= 派生状态推导（设计决策 2） =================

    def test_disp_status_derivation(self):
        base = {"status": models.STATUS_ACTIVE,
                "signup_deadline": "2026-01-10 18:00",
                "start_time": "2026-01-20 09:00"}
        self.assertEqual(disp_status_key(base, now="2026-01-10 18:00"), "open")   # 截止边界含
        self.assertEqual(disp_status_key(base, now="2026-01-11 00:00"), "closed")
        self.assertEqual(disp_status_key(base, now="2026-01-20 09:00"), "closed")  # 开始边界
        self.assertEqual(disp_status_key(base, now="2026-01-20 09:01"), "ongoing")
        cancelled = dict(base, status=models.STATUS_CANCELLED)
        self.assertEqual(disp_status_key(cancelled, now="2026-01-01 00:00"), "cancelled")
        finished = dict(base, status=models.STATUS_FINISHED)
        self.assertEqual(disp_status_key(finished, now="2026-01-01 00:00"), "finished")

    # ================= 注册占位冒烟（FR-1） =================

    def test_register_login_placeholder_smoke(self):
        c = self.app.test_client()
        r = c.post("/register", data={"username": "stu9", "nickname": "小九",
                                      "password": "123456", "password2": "123456",
                                      "role": "student"}, follow_redirects=True)
        self.assertIn("注册成功", r.get_data(as_text=True))
        # 重名被拒
        r = c.post("/register", data={"username": "stu9", "nickname": "x",
                                      "password": "123456", "password2": "123456",
                                      "role": "student"}, follow_redirects=True)
        self.assertIn("已被注册", r.get_data(as_text=True))
        # 登录成功 / 密码错误
        c.post("/login", data={"username": "stu9", "password": "123456"})
        self.assertTrue(session_uid(c))
        c.post("/logout")
        c.post("/login", data={"username": "stu9", "password": "badpass"})
        self.assertIsNone(session_uid(c))


def session_uid(client):
    with client.session_transaction() as s:
        return s.get("user_id")


if __name__ == "__main__":
    unittest.main(verbosity=2)
