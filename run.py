# 灵境人机协同自适应理性决策辅助系统 V3.5.1
# 模型系统实现

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("「灵境」人机协同自适应理性决策辅助系统 V3.5.1")
    print("=" * 60)
    print("系统启动中...")
    app.run(host='0.0.0.0', port=5000, debug=True)
