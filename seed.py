"""生成演示数据：python seed.py

账号(密码均为 123456，哈希存储)：
  教师 teacher01 王老师 · teacher02 陈老师
  学生 student01 小明 · student02 小红 · student03 小刚
活动时间相对"运行当天"自动生成，覆盖五种展示状态：
  报名中(名额充足 / 名额已满)/ 报名截止 / 进行中 / 已结束 / 已取消
重复运行前请先删除 instance/campus.db(或看到提示即停止)。
"""
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from app import create_app, models


def day(hours=10, delta=0):
    """相对今天偏移 delta 天的 hours 点整（delta 为负表示过去）。"""
    return (datetime.now() + timedelta(days=delta)).replace(hour=hours, minute=0,
                                                            second=0, microsecond=0)


def fmt(dt):
    return dt.strftime(models.TIME_FMT)


def main():
    app = create_app()
    with app.app_context():
        if models.get_user_by_username("teacher01"):
            print("检测到 instance/campus.db 已有数据，跳过种子生成。")
            print("如需重新生成：删除 instance/campus.db 后再次运行 python seed.py")
            return

        print("生成演示数据…")
        # ---- 账号 ----
        t1 = models.create_user("teacher01", generate_password_hash("123456"),
                                "teacher", "王老师")
        t2 = models.create_user("teacher02", generate_password_hash("123456"),
                                "teacher", "陈老师")
        s1 = models.create_user("student01", generate_password_hash("123456"),
                                "student", "小明")
        s2 = models.create_user("student02", generate_password_hash("123456"),
                                "student", "小红")
        s3 = models.create_user("student03", generate_password_hash("123456"),
                                "student", "小刚")
        print("[OK] 账号：teacher01/02(教师)、student01~03(学生)，密码 123456")

        def add(title, desc, loc, teacher, start, deadline, capacity=0):
            return models.create_activity(title=title, description=desc,
                                          location=loc, teacher_id=teacher,
                                          start_time=fmt(start),
                                          signup_deadline=fmt(deadline),
                                          capacity=capacity)

        # ---- 活动 ----
        a_open = add("人工智能前沿讲座", "介绍大语言模型与智能体(Agent)的最新进展与应用场景。",
                     "图书馆报告厅", t1, day(hours=14, delta=7), day(hours=20, delta=3))
        a_full = add("校园马拉松 5 公里", "环绕校园跑 5 公里，提供补给站与完赛证书。名额有限。",
                     "东区操场集合", t1, day(hours=8, delta=10), day(hours=22, delta=1), 2)
        add("摄影基础工作坊", "相机操作与构图入门，请自带设备。", "艺术楼 A-201", t1,
            day(hours=15, delta=5), day(hours=12, delta=-1))          # 报名截止
        add("编程入门分享会", "从零开始写第一个 Python 小程序。", "信息楼 305", t1,
            day(hours=19, delta=-1), day(hours=18, delta=-2))         # 进行中
        a_fin = add("春季社团嘉年华", "各社团摆摊展示与纳新，凭学生证入场。", "中心广场", t1,
                    day(hours=10, delta=-7), day(hours=18, delta=-8))
        a_cancel = add("篮球友谊赛", "大二 VS 大三 5v5 友谊赛，欢迎观战。", "体育馆", t1,
                       day(hours=16, delta=4), day(hours=18, delta=2))
        add("期中复习讲座(高等数学)", "重点题型梳理与答疑。", "教学楼 102", t2,
            day(hours=19, delta=6), day(hours=20, delta=4))           # teacher02 发布

        # ---- 报名关系(使列表覆盖"已报名""满员""名单非空") ----
        models.add_registration(a_open, s1)
        models.add_registration(a_open, s2)
        models.add_registration(a_full, s1)
        models.add_registration(a_full, s2)     # capacity=2 → 已满员
        models.add_registration(a_fin, s1)
        models.add_registration(a_fin, s3)
        models.set_activity_status(a_fin, models.STATUS_FINISHED)     # 已结束
        models.set_activity_status(a_cancel, models.STATUS_CANCELLED)  # 已取消
        models.add_registration(a_open, s3)     # 供"已报名"标识示例

        print("[OK] 活动 7 个：报名中×2(1 个满员)、报名截止、进行中、已结束、已取消、教师02发布各 1")
        print("完成。启动：python run.py  →  http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
