"""应用配置。"""
import os

# 项目根目录（campus_activity/）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 数据库默认位置：campus_activity/instance/campus.db（instance/ 不入库）
DEFAULT_DATABASE = os.path.join(BASE_DIR, "instance", "campus.db")

# 开发默认密钥：仅用于本地演示，生产环境务必用环境变量 SECRET_KEY 覆盖
DEFAULT_SECRET_KEY = "campus-activity-v1-dev-key"


def init_app_config(app):
    """写入应用配置（测试可通过 create_app(test_config=...) 覆盖）。"""
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY),
        DATABASE=os.environ.get("CAMPUS_DB", DEFAULT_DATABASE),
        # 阻止跨站请求携带会话 Cookie（基础 CSRF 缓解）
        SESSION_COOKIE_SAMESITE="Lax",
    )
