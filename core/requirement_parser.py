# 需求解析与风险分级模块 (Module 1)
# 负责需求标准化拆解与风险等级精准判定

import json
import uuid
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

from core.kernel import GradientKernel, RiskGrade, KernelLayer
from core.ai_client import LLMClient, LingjingPrompts, LLMMessage


@dataclass
class DecisionRequirement:
    """决策需求标准化结构"""
    decision_id: str
    user_id: str
    original_input: str            # 用户原始输入
    decision_goal: str = ""        # 决策目标
    boundary_scope: str = ""       # 边界范围
    precision_requirement: str = "" # 精度要求
    risk_exposure: str = ""        # 风险敞口
    constraints: str = ""          # 约束条件
    budget: str = ""               # 预算/金额
    time_cycle: str = ""           # 时间周期
    industry: str = "默认"         # 所属行业
    additional_info: Dict = field(default_factory=dict)  # 额外信息
    
    def to_dict(self):
        return asdict(self)


@dataclass
class RiskGradingResult:
    """风险分级结果"""
    decision_id: str
    risk_grade: str = ""            # low/medium/high
    risk_score: float = 0.0         # 0-10分
    irreversibility_score: float = 0.0
    compliance_score: float = 0.0
    complexity_score: float = 0.0
    weights_used: Dict = field(default_factory=dict)
    grading_basis: str = ""        # 定级依据说明
    execution_process: str = ""    # 对应执行流程
    estimated_time: str = ""       # 预计响应时间
    industry_baseline: str = ""    # 行业基准线
    user_confirmed: bool = False   # 用户是否确认
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)


class RequirementParser:
    """需求解析器 - 将自然语言需求拆解为标准化结构"""

    # 关键词映射
    GOAL_KEYWORDS = ["决定", "决策", "选择", "判断", "是否", "要不要", "该不该", "如何", "怎样", "方案", "规划"]
    BUDGET_KEYWORDS = ["万元", "万", "元", "预算", "资金", "金额", "投入", "花费"]
    TIME_KEYWORDS = ["期限", "周期", "时间", "年", "月", "天", "周", "长期", "短期", "中期"]
    RISK_KEYWORDS = ["风险承受", "风险能力", "承受能力", "保守", "激进", "稳健", "中等", "低风险", "高风险"]
    CONSTRAINT_KEYWORDS = ["约束", "限制", "条件", "要求", "前提", "不能", "必须", "不可"]
    
    def __init__(self, kernel: GradientKernel, ai_client: LLMClient = None):
        self.kernel = kernel
        self.ai_client = ai_client  # AI 客户端（可选，有则用 LLM 深度解析）
    
    def parse(self, user_input: str, user_id: str = "anonymous") -> DecisionRequirement:
        """解析用户自然语言需求（先规则提取，再 LLM 深度解析补充）"""
        decision_id = f"DEC-{uuid.uuid4().hex[:12].upper()}"
        req = DecisionRequirement(
            decision_id=decision_id,
            user_id=user_id,
            original_input=user_input
        )
        
        # 1. 规则引擎快速提取
        self._rule_based_extract(req, user_input)
        
        # 2. LLM 深度解析（如果 AI 可用）
        if self.ai_client and self.ai_client.is_available():
            ai_analysis = self._ai_deep_analysis(user_input)
            if ai_analysis:
                self._merge_ai_analysis(req, ai_analysis)
        
        return req
    
    def _rule_based_extract(self, req: DecisionRequirement, user_input: str):
        """基于规则的快速提取"""
        
        # 提取金额
        budget_match = re.search(r'([\d.]+)\s*(万元|万|元)?', user_input)
        if budget_match:
            amount = float(budget_match.group(1))
            unit = budget_match.group(2) or ""
            req.budget = f"{amount}{unit}"
            req.risk_exposure = f"潜在风险敞口：{amount}{unit}"
        
        # 提取时间周期
        time_match = re.search(r'(\d+)\s*(年|月|天|周|个季度)', user_input)
        if time_match:
            req.time_cycle = f"{time_match.group(1)}{time_match.group(2)}"
        
        # 识别行业
        industry_map = {
            "投资": "金融投资", "股票": "金融投资", "基金": "金融投资", "理财": "金融投资",
            "贷款": "金融投资", "期货": "金融投资", "融资": "金融投资", "并购": "金融投资",
            "合同": "法律合规", "诉讼": "法律合规", "法律": "法律合规", "合规": "法律合规",
            "医疗": "医疗健康", "健康": "医疗健康", "疾病": "医疗健康", "用药": "医疗健康",
            "房产": "房地产", "购房": "房地产", "租房": "房地产", "楼盘": "房地产",
            "创业": "企业战略", "战略": "企业战略", "项目": "企业战略", "团队": "企业战略"
        }
        for keyword, industry in industry_map.items():
            if keyword in user_input:
                req.industry = industry
                break
        
        # 提取决策目标（取输入的核心内容作为目标）
        req.decision_goal = user_input.strip()
        
        # 提取约束条件
        constraints = []
        if "不" in user_input or "不能" in user_input or "禁止" in user_input:
            for seg in user_input.split("，"):
                if any(k in seg for k in ["不", "不能", "禁止", "不投资", "不考虑"]):
                    constraints.append(seg.strip())
        if constraints:
            req.constraints = "；".join(constraints)

    def _ai_deep_analysis(self, user_input: str) -> Optional[Dict]:
        """调用 LLM 做需求深度语义解析"""
        try:
            messages = LingjingPrompts.build_requirement_analysis(user_input)
            resp = self.ai_client.chat_json(messages, temperature=0.2)
            if resp.success and resp.content:
                # 尝试解析 JSON
                content = resp.content.strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    content = "\n".join(lines)
                return json.loads(content)
        except Exception:
            pass
        return None

    def _merge_ai_analysis(self, req: DecisionRequirement, analysis: Dict):
        """将 AI 分析结果合并到需求结构中（AI 分析补充，规则提取优先）"""
        if analysis.get("decision_goal") and not req.decision_goal:
            req.decision_goal = analysis["decision_goal"]
        if analysis.get("boundary_scope") and not req.boundary_scope:
            req.boundary_scope = analysis["boundary_scope"]
        if analysis.get("precision_requirement"):
            req.precision_requirement = analysis["precision_requirement"]
        if analysis.get("risk_exposure") and not req.risk_exposure:
            req.risk_exposure = analysis["risk_exposure"]
        if analysis.get("constraints") and not req.constraints:
            req.constraints = analysis["constraints"]
        if analysis.get("industry") and analysis["industry"] != "默认":
            req.industry = analysis["industry"]
        # 存储额外 AI 分析信息
        req.additional_info.update({
            "ai_analysis": True,
            "emotion_tone": analysis.get("emotion_tone", ""),
            "information_completeness": analysis.get("information_completeness", ""),
            "missing_info": analysis.get("missing_info", []),
            "core_dilemma": analysis.get("core_dilemma", ""),
            "ai_summary": analysis.get("summary", "")
        })
        
        return req
    
    def _extract_goal(self, text: str) -> str:
        """提取决策目标"""
        sentences = re.split(r'[，。！？；]', text)
        goals = [s.strip() for s in sentences if any(k in s for k in self.GOAL_KEYWORDS)]
        return goals[0] if goals else text[:100]


class RiskGrader:
    """风险分级器 - 微量化打分模型"""
    
    # 行业强制高风险关键词
    HIGH_RISK_INDUSTRY_KEYWORDS = {
        "金融投资": [("金额", 50000), ("万元", 5)],
        "法律合规": ["合同审核", "诉讼", "合规风险"],
        "医疗健康": ["诊断", "用药", "手术", "治疗"],
        "房地产": [("金额", 500000), ("万元", 50)]
    }
    
    def __init__(self, kernel: GradientKernel):
        self.kernel = kernel
    
    def grade(self, requirement: DecisionRequirement) -> RiskGradingResult:
        """执行风险分级"""
        result = RiskGradingResult(
            decision_id=requirement.decision_id
        )
        
        industry = requirement.industry
        rules = self.kernel.get_risk_grading_rules(industry)
        
        # 获取行业适配权重
        weights = {}
        for dim_key, dim_val in rules["dimensions"].items():
            weights[dim_key] = dim_val.get("current_weight", dim_val["weight"])
        result.weights_used = weights
        
        # ---- 决策不可逆程度评分 ----
        irrev_score = 3.0  # 基准分
        if requirement.budget:
            amount = self._extract_amount(requirement.budget)
            if amount >= 500000:
                irrev_score = 9.0
            elif amount >= 100000:
                irrev_score = 8.0
            elif amount >= 50000:
                irrev_score = 7.0
            elif amount >= 10000:
                irrev_score = 5.0
            else:
                irrev_score = 3.0
        
        if industry in ["企业战略", "房地产"]:
            irrev_score = min(irrev_score + 1.0, 10.0)
        
        result.irreversibility_score = irrev_score
        
        # ---- 合规与专业度评分 ----
        comp_score = 2.0
        if industry == "金融投资":
            comp_score = 7.0
        elif industry == "法律合规":
            comp_score = 8.0
        elif industry == "医疗健康":
            comp_score = 8.0
        elif industry == "房地产":
            comp_score = 5.0
        elif industry == "企业战略":
            comp_score = 4.0
        
        result.compliance_score = comp_score
        
        # ---- 信息完整度与场景复杂度评分 ----
        cx_score = 4.0
        if not requirement.budget:
            cx_score += 1.5  # 缺少预算信息
        if not requirement.time_cycle:
            cx_score += 1.0  # 缺少时间周期
        if not requirement.constraints:
            cx_score += 0.5
        if industry == "企业战略":
            cx_score += 1.5  # 企业战略天然复杂
        
        result.complexity_score = min(cx_score, 10.0)
        
        # ---- 计算综合得分 ----
        total_score = (
            irrev_score * weights.get("irreversibility", 0.40) +
            comp_score * weights.get("compliance", 0.35) +
            cx_score * weights.get("complexity", 0.25)
        )
        result.risk_score = round(total_score, 2)
        
        # ---- 行业强制定级检查 ----
        forced_high = self._check_industry_forced_high(requirement)
        
        # ---- 确定风险等级 ----
        if forced_high:
            result.risk_grade = RiskGrade.HIGH.value
            result.industry_baseline = f"行业强制高风险：{forced_high}"
        elif result.risk_score < 3.5:
            result.risk_grade = RiskGrade.LOW.value
        elif result.risk_score < 6.5:
            result.risk_grade = RiskGrade.MEDIUM.value
        else:
            result.risk_grade = RiskGrade.HIGH.value
        
        # ---- 设置执行流程与预计时间 ----
        process_map = {
            RiskGrade.LOW.value: ("3步极简SOP", "≤5秒"),
            RiskGrade.MEDIUM.value: ("5步标准SOP", "≤30秒"),
            RiskGrade.HIGH.value: ("7步强校验SOP", "≤2分钟"),
            RiskGrade.EMERGENCY.value: ("紧急绿色通道", "≤10秒")
        }
        process, time_est = process_map.get(result.risk_grade, ("标准SOP", "≤30秒"))
        result.execution_process = process
        result.estimated_time = time_est
        
        # ---- 生成定级依据说明 ----
        result.grading_basis = (
            f"综合评分：{result.risk_score}/10\n"
            f"• 决策不可逆程度：{result.irreversibility_score}/10（权重{weights.get('irreversibility', 0.40)*100:.0f}%）\n"
            f"• 合规与专业度要求：{result.compliance_score}/10（权重{weights.get('compliance', 0.35)*100:.0f}%）\n"
            f"• 信息完整度与复杂度：{result.complexity_score}/10（权重{weights.get('complexity', 0.25)*100:.0f}%）\n"
            f"• 所属行业：{industry}"
        )
        if forced_high:
            result.grading_basis += f"\n• 行业强制定级：{forced_high}"
        
        return result
    
    def _extract_amount(self, budget_str: str) -> float:
        """从预算字符串提取金额（统一转为元）"""
        match = re.search(r'([\d.]+)\s*(万元|万|元)?', budget_str)
        if not match:
            return 0
        amount = float(match.group(1))
        unit = match.group(2) or "元"
        if unit in ["万元", "万"]:
            amount *= 10000
        return amount
    
    def _check_industry_forced_high(self, req: DecisionRequirement) -> Optional[str]:
        """检查行业强制高风险规则"""
        industry = req.industry
        rules = self.kernel._risk_rules.get("industry_baselines", {})
        
        if industry in rules:
            baseline = rules[industry]
            trigger = baseline.get("高风险触发", "")
            forced_scenes = baseline.get("高风险强制场景", [])
            
            # 检查金额触发
            amount = self._extract_amount(req.budget) if req.budget else 0
            if "5万元" in trigger and amount >= 50000:
                return trigger
            if "50万元" in trigger and amount >= 500000:
                return trigger
            if "合同审核" in trigger and any(s in req.original_input for s in forced_scenes):
                return trigger
            if "诊疗" in trigger and any(s in req.original_input for s in forced_scenes):
                return trigger
        
        return None
    
    def appeal_risk_grade(self, result: RiskGradingResult) -> Dict:
        """风险等级申诉机制"""
        if result.risk_grade != RiskGrade.HIGH.value:
            return {"success": False, "message": "仅高风险需求可申请下调"}
        
        return {
            "success": True,
            "message": "高风险需求可下调至中风险",
            "requirements": [
                "用户需签署《风险自担确认书》",
                "绝对禁止下调至低风险",
                "下调后仍需执行三维平行校验"
            ],
            "new_grade": RiskGrade.MEDIUM.value,
            "confirmation_text": "我已知晓该决策存在高风险，自愿将风险等级下调至中风险，并承担由此产生的全部损失与责任。"
        }
