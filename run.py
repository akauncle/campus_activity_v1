"""启动入口：python run.py → http://127.0.0.1:5000"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # debug=True：修改代码自动重载，便于课堂演示；正式部署请关闭
    app.run(debug=True, host="127.0.0.1", port=5000)
