# 灵境系统配置
import os

class Config:
    """基础配置"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'lingjing-v351-secret-key-2026')
    VERSION = 'V3.5.1'
    SYSTEM_NAME = '灵境人机协同自适应理性决策辅助系统'
    
    # AI模型配置（使用OpenAI兼容接口）
    AI_API_BASE = os.environ.get('AI_API_BASE', 'https://api.openai.com/v1')
    AI_API_KEY = os.environ.get('AI_API_KEY', '')
    AI_MODEL_PRIMARY = os.environ.get('AI_MODEL_PRIMARY', 'gpt-4o')
    AI_MODEL_CHECK_1 = os.environ.get('AI_MODEL_CHECK_1', 'gpt-4o')
    AI_MODEL_CHECK_2 = os.environ.get('AI_MODEL_CHECK_2', 'gpt-4o-mini')
    AI_MODEL_CHECK_3 = os.environ.get('AI_MODEL_CHECK_3', 'gpt-4o')
    
    # 数据存储
    DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    LEDGER_DIR = os.path.join(DATA_DIR, 'ledgers')
    CASE_DIR = os.path.join(DATA_DIR, 'cases')
    RULES_DIR = os.path.join(DATA_DIR, 'rules')
    
    # 限流配置
    RATE_LIMIT_PERSONAL = 10  # 次/分钟
    RATE_LIMIT_TEAM = 50
    RATE_LIMIT_ENTERPRISE = 200
