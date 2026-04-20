# 灵境系统 - Flask 应用

from flask import Flask
from flask_cors import CORS
from config import Config
import os

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)
    CORS(app)

    # 确保数据目录存在
    for d in [Config.DATA_DIR, Config.LEDGER_DIR, Config.CASE_DIR, Config.RULES_DIR]:
        os.makedirs(d, exist_ok=True)

    # 注册蓝图（API路由）
    from routes.decision import decision_bp
    from routes.system import system_bp

    app.register_blueprint(decision_bp, url_prefix='/api/v1/decision')
    app.register_blueprint(system_bp, url_prefix='/api/v1')

    @app.route('/')
    def index():
        from flask import render_template
        return render_template('index.html')

    return app

# 直接创建 app 实例（供 gunicorn 使用）
app = create_app()
