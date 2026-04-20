# 决策API路由
from flask import Blueprint, request, jsonify
from config import Config
from typing import Dict, Optional

decision_bp = Blueprint('decision', __name__)

# 全局内核实例
from core import GradientKernel, RequirementParser, RiskGrader
from core import ParallelCheckEngine, SchemeOutput
from core import MetaMonitor, OutputFormatter
from core.ai_client import LLMClient, LingjingPrompts
from core.scheme_generator import AISchemeGenerator

# 初始化核心组件
kernel = GradientKernel()
ai_client = LLMClient()  # AI 客户端（从 Config 读取配置）

# 注入 AI 客户端到各模块
parser = RequirementParser(kernel, ai_client=ai_client)
grader = RiskGrader(kernel)
check_engine = ParallelCheckEngine(kernel, ai_client=ai_client)
meta_monitor = MetaMonitor(kernel, Config.LEDGER_DIR)
output_formatter = OutputFormatter(kernel)
scheme_generator = AISchemeGenerator(ai_client)

# 存储会话状态
_sessions = {}


@decision_bp.route('/risk-grade', methods=['POST'])
def risk_grade():
    """需求拆解与风险分级"""
    data = request.get_json()
    user_input = data.get('decision_goal', '')
    user_id = data.get('user_id', 'anonymous')

    if not user_input.strip():
        return jsonify({
            "code": 4001,
            "message": "决策需求不能为空",
            "data": None
        })

    # 1. 红线检查
    violated, violation = kernel.check_red_line_violation(user_input, user_id)
    if violated:
        return jsonify({
            "code": 4003,
            "message": violation["message"],
            "data": {"violation": violation}
        })

    # 2. 需求解析（含 AI 深度解析）
    requirement = parser.parse(user_input, user_id)

    # 3. 风险分级
    grading = grader.grade(requirement)

    # 4. 检查规则冲突
    industries = [requirement.industry]
    conflict = kernel.check_rule_conflict(industries)

    # 保存会话
    _sessions[requirement.decision_id] = {
        "requirement": requirement,
        "grading": grading,
        "confirmed": False
    }

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "decision_id": requirement.decision_id,
            "requirement": requirement.to_dict(),
            "risk_grading": grading.to_dict(),
            "rule_conflict": conflict,
            "ai_available": ai_client.is_available(),
            "execution_process": grading.execution_process,
            "estimated_time": grading.estimated_time,
            "next_step": "请确认风险等级与需求边界，确认后系统将执行对应流程"
        }
    })


@decision_bp.route('/scheme-generate', methods=['POST'])
def scheme_generate():
    """决策方案生成（AI 驱动）"""
    data = request.get_json()
    decision_id = data.get('decision_id', '')
    user_id = data.get('user_id', 'anonymous')

    session = _sessions.get(decision_id)
    if not session:
        return jsonify({"code": 4008, "message": "决策ID不存在", "data": None})

    requirement = session["requirement"]
    grading = session["grading"]
    risk_grade = grading.risk_grade

    # 使用 AI 方案生成器
    schemes = scheme_generator.generate_schemes(
        requirement=requirement,
        risk_grade=risk_grade,
        user_input=requirement.original_input
    )

    session["schemes"] = schemes

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "decision_id": decision_id,
            "scheme_count": len(schemes),
            "schemes": [s.to_dict() for s in schemes],
            "ai_generated": ai_client.is_available(),
            "next_step": "方案已生成，将执行平行校验"
        }
    })


@decision_bp.route('/parallel-check', methods=['POST'])
def parallel_check():
    """三维平行校验（规则 + AI 混合）"""
    data = request.get_json()
    decision_id = data.get('decision_id', '')

    session = _sessions.get(decision_id)
    if not session or "schemes" not in session:
        return jsonify({"code": 4008, "message": "决策ID不存在或方案未生成", "data": None})

    grading = session["grading"]
    risk_grade = grading.risk_grade

    all_check_results = {}
    for scheme in session["schemes"]:
        result = check_engine.execute_parallel_check(
            scheme=scheme,
            original_requirement=session["requirement"].original_input,
            risk_grade=risk_grade
        )
        all_check_results[scheme.scheme_id] = result

    session["check_results"] = all_check_results

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "decision_id": decision_id,
            "risk_grade": risk_grade,
            "check_results": all_check_results,
            "ai_checked": ai_client.is_available(),
            "overall_status": "通过" if all(r.get("overall_result") in ["pass", "pass_with_issues", "pass_with_notes", "pass_with_warning"] for r in all_check_results.values()) else "需整改",
            "next_step": "校验完成，将执行元监监查"
        }
    })


@decision_bp.route('/meta-monitor', methods=['POST'])
def meta_monitor_check():
    """元监合规监查 + 台账生成"""
    data = request.get_json()
    decision_id = data.get('decision_id', '')
    user_id = data.get('user_id', 'anonymous')

    session = _sessions.get(decision_id)
    if not session:
        return jsonify({"code": 4008, "message": "决策ID不存在", "data": None})

    requirement = session["requirement"]
    grading = session["grading"]
    schemes = session.get("schemes", [])
    check_results = session.get("check_results", {})

    # 汇总校验结果
    merged_check = {
        "checks": {},
        "overall_result": "pass",
        "red_flags": [],
        "issues_summary": [],
        "resolution": ""
    }
    for scheme_id, cr in check_results.items():
        merged_check["checks"].update(cr.get("checks", {}))
        merged_check["red_flags"].extend(cr.get("red_flags", []))
        merged_check["issues_summary"].extend(cr.get("issues_summary", []))
        if cr.get("overall_result") not in ["pass", "pass_with_issues", "pass_with_notes"]:
            merged_check["overall_result"] = cr.get("overall_result")

    # 执行元监
    monitor_report = meta_monitor.execute_monitor(
        decision_id=decision_id,
        risk_grade=grading.risk_grade,
        requirement=requirement.original_input,
        scheme_outputs=schemes,
        check_result=merged_check,
        user_id=user_id
    )

    # 生成台账
    cognitive_biases = []
    industry_rules = kernel.get_industry_rules(requirement.industry)
    if industry_rules:
        cognitive_biases = industry_rules.get("cognitive_biases", [])

    ledger = meta_monitor.generate_ledger(
        decision_id=decision_id,
        user_id=user_id,
        risk_grade=grading.risk_grade,
        requirement_summary=requirement.decision_goal,
        risk_grading_detail=grading.to_dict(),
        schemes=schemes,
        check_result=merged_check,
        monitor_report=monitor_report,
        risk_warnings=merged_check["red_flags"],
        cognitive_bias_alerts=cognitive_biases
    )

    session["monitor_report"] = monitor_report
    session["ledger"] = ledger

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "decision_id": decision_id,
            "monitor_report": monitor_report.to_dict(),
            "ledger_id": ledger.ledger_id,
            "ledger_hash": ledger.content_hash,
            "overall_status": monitor_report.overall_result
        }
    })


@decision_bp.route('/final-output', methods=['POST'])
def final_output():
    """全景决策辅助输出"""
    data = request.get_json()
    decision_id = data.get('decision_id', '')

    session = _sessions.get(decision_id)
    if not session:
        return jsonify({"code": 4008, "message": "决策ID不存在", "data": None})

    requirement = session["requirement"]
    grading = session["grading"]
    schemes = session.get("schemes", [])
    check_results = session.get("check_results", {})
    monitor_report = session.get("monitor_report")

    risk_grade = grading.risk_grade

    # 合并校验结果
    merged_check = {
        "checks": {},
        "overall_result": "pass",
        "red_flags": [],
        "issues_summary": [],
        "resolution": ""
    }
    for scheme_id, cr in check_results.items():
        merged_check["checks"].update(cr.get("checks", {}))
        merged_check["red_flags"].extend(cr.get("red_flags", []))
        merged_check["issues_summary"].extend(cr.get("issues_summary", []))

    # 尝试用 AI 整合输出
    integrated_output = None
    if ai_client.is_available():
        try:
            integrated_output = _ai_integrate_output(
                requirement.original_input, risk_grade, schemes,
                merged_check, requirement.additional_info
            )
        except Exception:
            integrated_output = None

    # 根据风险等级格式化输出
    if risk_grade == "low":
        if integrated_output:
            output = output_formatter.format_low_risk_output(integrated_output)
        else:
            output = output_formatter.format_low_risk_output(
                scheme_content=schemes[0].raw_content if schemes else ""
            )
    elif risk_grade == "medium":
        industry_rules = kernel.get_industry_rules(requirement.industry)
        cognitive_biases = industry_rules.get("cognitive_biases", []) if industry_rules else []
        scheme_content = integrated_output or "\n".join(s.raw_content for s in schemes)
        output = output_formatter.format_medium_risk_output(
            scheme_content=scheme_content,
            check_result=merged_check,
            risk_warnings=merged_check["red_flags"],
            cognitive_biases=cognitive_biases,
            industry=requirement.industry
        )
    elif risk_grade == "emergency":
        output = output_formatter.format_emergency_output(
            preliminary_scheme=integrated_output or (schemes[0].raw_content if schemes else ""),
            risk_summary="；".join(merged_check["red_flags"][:3])
        )
    else:  # high
        industry_rules = kernel.get_industry_rules(requirement.industry)
        cognitive_biases = industry_rules.get("cognitive_biases", []) if industry_rules else []
        output = output_formatter.format_high_risk_output(
            schemes=schemes,
            check_result=merged_check,
            monitor_report=monitor_report.to_dict() if monitor_report else {},
            risk_warnings=merged_check["red_flags"],
            cognitive_biases=cognitive_biases,
            data_verification=monitor_report.data_verification if monitor_report else [],
            industry=requirement.industry
        )
    
    # 如果 AI 生成了整合报告，附加到输出中
    if integrated_output:
        output["ai_integrated_report"] = integrated_output

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": output
    })


@decision_bp.route('/full-pipeline', methods=['POST'])
def full_pipeline():
    """一键执行全流程（AI 驱动版）"""
    data = request.get_json()
    user_input = data.get('decision_goal', '')
    user_id = data.get('user_id', 'anonymous')

    if not user_input.strip():
        return jsonify({"code": 4001, "message": "决策需求不能为空", "data": None})

    # 1. 红线检查
    violated, violation = kernel.check_red_line_violation(user_input, user_id)
    if violated:
        return jsonify({
            "code": 4003,
            "message": violation["message"],
            "data": {"violation": violation}
        })

    # 2. 需求解析 + 风险分级（含 AI 深度解析）
    requirement = parser.parse(user_input, user_id)
    grading = grader.grade(requirement)
    risk_grade = grading.risk_grade

    # 3. AI 方案生成
    schemes = scheme_generator.generate_schemes(
        requirement=requirement,
        risk_grade=risk_grade,
        user_input=user_input
    )

    # 4. 平行校验（规则 + AI 混合）
    check_result = check_engine.execute_parallel_check(
        scheme=schemes[0],
        original_requirement=user_input,
        risk_grade=risk_grade
    )
    for s in schemes[1:]:
        cr = check_engine.execute_parallel_check(s, user_input, risk_grade)
        check_result["checks"].update(cr.get("checks", {}))
        check_result["red_flags"].extend(cr.get("red_flags", []))
        check_result["issues_summary"].extend(cr.get("issues_summary", []))

    # 5. 元监
    monitor_report = meta_monitor.execute_monitor(
        decision_id=requirement.decision_id,
        risk_grade=risk_grade,
        requirement=user_input,
        scheme_outputs=schemes,
        check_result=check_result,
        user_id=user_id
    )

    # 6. 生成台账
    industry_rules = kernel.get_industry_rules(requirement.industry)
    cognitive_biases = industry_rules.get("cognitive_biases", []) if industry_rules else []

    ledger = meta_monitor.generate_ledger(
        decision_id=requirement.decision_id,
        user_id=user_id,
        risk_grade=risk_grade,
        requirement_summary=requirement.decision_goal,
        risk_grading_detail=grading.to_dict(),
        schemes=schemes,
        check_result=check_result,
        monitor_report=monitor_report,
        risk_warnings=check_result["red_flags"],
        cognitive_bias_alerts=cognitive_biases
    )

    # 7. 格式化输出
    # 尝试 AI 整合报告
    integrated_report = None
    if ai_client.is_available():
        try:
            integrated_report = _ai_integrate_output(
                user_input, risk_grade, schemes,
                check_result, requirement.additional_info
            )
        except Exception:
            integrated_report = None

    if risk_grade == "low":
        output = output_formatter.format_low_risk_output(
            integrated_report or (schemes[0].raw_content if schemes else "")
        )
    elif risk_grade == "medium":
        output = output_formatter.format_medium_risk_output(
            scheme_content=integrated_report or "\n".join(s.raw_content for s in schemes),
            check_result=check_result,
            risk_warnings=check_result["red_flags"],
            cognitive_biases=cognitive_biases,
            industry=requirement.industry
        )
    else:
        output = output_formatter.format_high_risk_output(
            schemes=schemes,
            check_result=check_result,
            monitor_report=monitor_report.to_dict(),
            risk_warnings=check_result["red_flags"],
            cognitive_biases=cognitive_biases,
            data_verification=monitor_report.data_verification,
            industry=requirement.industry
        )

    if integrated_report:
        output["ai_integrated_report"] = integrated_report

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "decision_id": requirement.decision_id,
            "requirement": requirement.to_dict(),
            "risk_grading": grading.to_dict(),
            "schemes": [s.to_dict() for s in schemes],
            "check_result": check_result,
            "monitor_report": monitor_report.to_dict(),
            "ledger": {
                "ledger_id": ledger.ledger_id,
                "content_hash": ledger.content_hash
            },
            "final_output": output,
            "ai_integrated_report": integrated_report,
            "ai_available": ai_client.is_available(),
            "pipeline_status": "completed"
        }
    })


@decision_bp.route('/ledger-generate', methods=['POST'])
def ledger_generate():
    """决策台账生成（独立接口）"""
    data = request.get_json()
    decision_id = data.get('decision_id', '')
    user_id = data.get('user_id', 'anonymous')

    session = _sessions.get(decision_id)
    if not session or "ledger" not in session:
        return jsonify({"code": 4008, "message": "台账不存在，请先完成决策流程", "data": None})

    ledger = session["ledger"]
    integrity = meta_monitor.verify_ledger_integrity(ledger.ledger_id)

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "ledger_id": ledger.ledger_id,
            "content_hash": ledger.content_hash,
            "integrity": integrity,
            "ledger": ledger.to_dict()
        }
    })


@decision_bp.route('/ai-status', methods=['GET'])
def ai_status():
    """查看 AI 服务状态"""
    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "available": ai_client.is_available(),
            "model": Config.AI_MODEL_PRIMARY,
            "api_base": Config.AI_API_BASE,
            "api_key_configured": bool(Config.AI_API_KEY)
        }
    })


@decision_bp.route('/ai-status', methods=['POST'])
def ai_configure():
    """动态配置 AI（仅当次会话生效）"""
    data = request.get_json()
    api_key = data.get('api_key', '')
    api_base = data.get('api_base', '')
    model = data.get('model', '')

    if api_key:
        ai_client.api_key = api_key
    if api_base:
        ai_client.api_base = api_base
    if model:
        ai_client.default_model = model

    # 清除旧的 client 缓存以使用新配置
    ai_client._clients = {}

    # 同步更新全局依赖
    parser.ai_client = ai_client
    check_engine.ai_client = ai_client
    scheme_generator.ai_client = ai_client

    return jsonify({
        "code": 2000,
        "message": "success",
        "data": {
            "available": ai_client.is_available(),
            "model": ai_client.default_model,
            "api_base": ai_client.api_base
        }
    })


def _ai_integrate_output(
    user_input: str,
    risk_grade: str,
    schemes: list,
    check_results: Dict,
    requirement_analysis: Dict
) -> Optional[str]:
    """调用 AI 整合最终输出报告"""
    messages = LingjingPrompts.build_output_integration(
        user_input=user_input,
        risk_grade=risk_grade,
        schemes=[s.to_dict() for s in schemes],
        check_results=check_results,
        requirement_analysis=requirement_analysis
    )
    resp = ai_client.chat(messages, temperature=0.5, max_tokens=4096)
    if resp.success and resp.content.strip():
        return resp.content.strip()
    return None
