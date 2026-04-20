# 系统管理API路由
from flask import Blueprint, request, jsonify
from config import Config
from core.kernel import GradientKernel, RiskGrade

system_bp = Blueprint('system', __name__)

kernel = GradientKernel()


@system_bp.route('/auth/token', methods=['POST'])
def get_token():
    """获取访问令牌"""
    data = request.get_json()
    ak = data.get('ak', '')
    sk = data.get('sk', '')
    
    if not ak or not sk:
        return jsonify({"code": 4002, "message": "Access Key或Secret Key错误", "data": None})
    
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "token": f"lj_token_{ak[:8]}",
            "expires_in": 7200,
            "token_type": "Bearer"
        }
    })


@system_bp.route('/system/status', methods=['GET'])
def system_status():
    """系统状态检查"""
    integrity = kernel.validate_kernel_integrity()
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "system_name": "灵境人机协同自适应理性决策辅助系统",
            "version": Config.VERSION,
            "kernel_integrity": integrity,
            "red_lines_count": len(kernel.get_red_lines()),
            "risk_dimensions": 3,
            "cognitive_biases_count": len(kernel.get_cognitive_biases()),
            "supported_industries": list(kernel._industry_rules.keys()),
            "status": "running"
        }
    })


@system_bp.route('/red-lines', methods=['GET'])
def get_red_lines():
    """获取核心红线规则"""
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "red_lines": kernel.get_red_lines(),
            "total": len(kernel.get_red_lines())
        }
    })


@system_bp.route('/cognitive-biases', methods=['GET'])
def get_cognitive_biases():
    """获取认知偏差清单"""
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "cognitive_biases": kernel.get_cognitive_biases(),
            "total": len(kernel.get_cognitive_biases())
        }
    })


@system_bp.route('/risk-grading/rules', methods=['GET'])
def get_risk_grading_rules():
    """获取风险分级规则"""
    industry = request.args.get('industry', '默认')
    rules = kernel.get_risk_grading_rules(industry)
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": rules
    })


@system_bp.route('/industry-rules/<industry>', methods=['GET'])
def get_industry_rules(industry):
    """获取行业专项规则"""
    rules = kernel.get_industry_rules(industry)
    if not rules:
        return jsonify({"code": 4008, "message": f"未找到行业「{industry}」的专项规则", "data": None})
    
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": rules
    })


@system_bp.route('/check-violation', methods=['POST'])
def check_violation():
    """红线违规检查"""
    data = request.get_json()
    user_input = data.get('input', '')
    user_id = data.get('user_id', 'anonymous')
    
    violated, violation = kernel.check_red_line_violation(user_input, user_id)
    
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "violated": violated,
            "violation": violation
        }
    })


@system_bp.route('/rule-conflict', methods=['POST'])
def check_rule_conflict():
    """规则冲突检测"""
    data = request.get_json()
    industries = data.get('industries', [])
    
    conflict = kernel.check_rule_conflict(industries)
    
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "has_conflict": conflict is not None,
            "conflict_detail": conflict
        }
    })


@system_bp.route('/wakeup-prompt', methods=['GET'])
def get_wakeup_prompt():
    """获取系统唤醒Prompt"""
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "simplified": """# 系统唤醒指令
请你严格遵循《灵境人机协同自适应理性决策辅助系统V3.5.1》的核心规则，为我提供绝对中立、独立的决策辅助服务：
1. 最终决策权100%归我所有，你绝对不能替我做最终决策
2. 必须完整披露所有正向和反向信息，核心风险点占比不低于30%
3. 所有核心数据必须标注权威来源
4. 先拆解我的需求并完成风险分级，经我确认后再执行后续流程
5. 医疗、法律、金融等专业领域仅提供公开信息参考

我的决策需求：【填写你的具体需求】""",
            "full": """# 系统唤醒指令（完整版）
请你严格遵循《灵境人机协同自适应理性决策辅助系统V3.5.1》的全部规则...

## 一、不可突破的6条生死红线
1. 最终决策权100%归我所有
2. 生成与校验必须完全隔离
3. 必须完整披露所有正向和反向信息
4. 所有核心数据必须标注权威来源
5. 专业领域仅提供公开信息参考
6. 必须严格遵循风险分级对应的流程规则

## 二、平行校验角色规则
1. 前提依据校验官
2. 逻辑推导校验官
3. 框架与风险校验官

## 三、我的决策需求
【在这里填写你的具体决策需求】"""
        }
    })
