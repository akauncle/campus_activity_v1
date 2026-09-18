"""账号业务模块自动化测试（FR-1：注册 / 登录 / 登出 / 权限矩阵）。

运行：python -m unittest discover -s tests -v
与 02-工程意图 §5 完成判据 1/2 对应：注册校验的分支、密码不落明文、
会话键约定，以及"非本人角色不能做他人角色的事"的权限矩阵。
每个用例使用独立临时数据库，互不干扰。
"""
import os
import sqlite3
import tempfile
import unittest

from werkzeug.security import check_password_hash

from app import create_app, models
from app.auth import decorators

FORM = {"username": "stu9", "nickname": "小九", "password": "123456",
        "password2": "123456", "role": "student"}


class AuthTestCase(unittest.TestCase):
    """基类：每个用例一个临时库 + 一个已存在的教师账号。"""

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()
        with self.app.app_context():
            self.t1 = models.create_user("t1", "h", "teacher", "王老师")

    def tearDown(self):
        os.remove(self.db_path)

    # ---- 工具 ----
    def get_user(self, username):
        with self.app.app_context():
            return models.get_user_by_username(username)

    def count_users(self):
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        finally:
            conn.close()

    def session_uid(self):
        with self.client.session_transaction() as s:
            return s.get("user_id"), s.get("role")

    def login(self, uid, role):
        with self.client.session_transaction() as s:
            s["user_id"] = uid
            s["role"] = role

    def post(self, url, data, **kw):
        """POST 并返回文本响应（默认跟随重定向以便断言 flash 提示）。"""
        kw.setdefault("follow_redirects", True)
        return self.client.post(url, data=data, **kw).get_data(as_text=True)

    # ================= 注册：成功路径 =================

    def test_register_success_stores_hashed_password(self):
        html = self.post("/register", FORM)
        self.assertIn("注册成功", html)

        user = self.get_user("stu9")
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "student")
        self.assertEqual(user["nickname"], "小九")
        # 密码必须哈希存储：既不等于明文，也能通过校验函数验回
        self.assertNotEqual(user["password_hash"], "123456")
        self.assertNotIn("123456", user["password_hash"])
        self.assertTrue(check_password_hash(user["password_hash"], "123456"))

    def test_register_teacher_role_and_default_nickname(self):
        data = dict(FORM, username="tea9", nickname="", role="teacher")
        self.assertIn("注册成功", self.post("/register", data))

        user = self.get_user("tea9")
        self.assertEqual(user["role"], "teacher")
        self.assertEqual(user["nickname"], "tea9")   # 昵称留空则回退用户名

    def test_register_username_is_unique_across_roles(self):
        self.post("/register", FORM)                              # stu9 已存在
        html = self.post("/register", dict(FORM, role="teacher"))  # 换个身份再注册
        self.assertIn("已被注册", html)
        self.assertEqual(self.count_users(), 2)                   # t1 + stu9，未新增

    # ================= 注册：校验分支（失败一律不落库） =================

    def test_register_validation_errors(self):
        cases = {
            "用户名与密码不能为空": dict(FORM, username="  "),
            "密码至少 6 位": dict(FORM, password="123", password2="123"),
            "两次输入的密码不一致": dict(FORM, password2="654321"),
            "请选择身份": dict(FORM, role="admin"),
        }
        for expected, data in cases.items():
            with self.subTest(expected):
                html = self.post("/register", data)
                self.assertIn(expected, html)
        self.assertEqual(self.count_users(), 1)   # 仅 setUp 的 t1，全部未落库

    # ================= 登录 =================

    def test_login_success_writes_session_convention_keys(self):
        self.post("/register", FORM)
        html = self.post("/login", {"username": "stu9", "password": "123456"})

        self.assertIn("欢迎回来", html)
        uid, role = self.session_uid()
        self.assertEqual(uid, self.get_user("stu9")["id"])
        self.assertEqual(role, "student")          # 会话约定的两个键名

    def test_login_rejects_wrong_password_and_unknown_user(self):
        self.post("/register", FORM)
        for creds in ({"username": "stu9", "password": "badpass"},
                      {"username": "nobody", "password": "123456"}):
            with self.subTest(creds["username"]):
                html = self.post("/login", creds)
                self.assertIn("用户名或密码错误", html)
                self.assertEqual(self.session_uid(), (None, None))   # 不建立会话

    def test_logout_clears_session(self):
        self.post("/register", FORM)
        self.post("/login", {"username": "stu9", "password": "123456"})
        self.assertIsNotNone(self.session_uid()[0])

        html = self.post("/logout", {})
        self.assertIn("已退出登录", html)
        self.assertEqual(self.session_uid(), (None, None))

    def test_auth_pages_redirect_when_already_logged_in(self):
        self.login(self.t1, "teacher")
        for url in ("/login", "/register"):
            with self.subTest(url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302)
                self.assertIn("/activities", r.headers["Location"])

    # ================= 权限矩阵 =================

    def test_anonymous_operations_redirect_to_login(self):
        """未登录访问受保护路由 → 提示并引导登录，而不是 403。"""
        html = self.post("/activities/1/signup", {})
        self.assertIn("请先登录", html)
        self.assertEqual(self.session_uid(), (None, None))

    def test_anonymous_teacher_page_redirects_to_login(self):
        r = self.client.get("/activities/new")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_student_cannot_reach_teacher_routes(self):
        with self.app.app_context():
            self.s1 = models.create_user("s1", "h", "student", "小明")
        self.login(self.s1, "student")
        for url in ("/activities/new", "/activities/mine"):
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_teacher_cannot_sign_up_for_activity(self):
        with self.app.app_context():
            aid = models.create_activity(
                title="讲座", description="介绍", location="教室 A",
                teacher_id=self.t1, start_time="2099-01-02 09:00",
                signup_deadline="2099-01-01 18:00")
        self.login(self.t1, "teacher")
        self.assertEqual(self.client.post(f"/activities/{aid}/signup").status_code, 403)

    # ================= 装饰器单元行为 =================

    def test_decorator_helpers_read_session(self):
        with self.app.test_request_context("/"):
            from flask import session
            self.assertFalse(decorators.is_logged_in())
            self.assertIsNone(decorators.current_user_id())
            self.assertIsNone(decorators.current_role())
            session["user_id"], session["role"] = 7, "student"
            self.assertTrue(decorators.is_logged_in())
            self.assertEqual(decorators.current_user_id(), 7)
            self.assertEqual(decorators.current_role(), "student")


if __name__ == "__main__":
    unittest.main(verbosity=2)
