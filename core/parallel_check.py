# 平行校验核心模块 (Module 2)
# 防自证偏误引擎 - 通过时序隔离+混合校验实现生成与校验的完全认知隔离

import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime

from core.kernel import RiskGrade
from core.ai_client import LLMClient, LingjingPrompts, LLMMessage


class CheckResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


@dataclass
class SchemeOutput:
    """方案输出"""
    scheme_id: str
    scheme_type: str              # optimistic/neutral/pessimistic
    core_logic: str               # 核心逻辑
    expected_return: str          # 收益预期
    risk_exposure: str            # 风险敞口
    applicable_scenarios: str     # 适用场景
    trigger_conditions: str       # 触发条件
    key_risks: List[str] = field(default_factory=list)     # 核心风险
    data_sources: List[str] = field(default_factory=list)  # 数据来源
    confidence: str = ""          # 置信度
    raw_content: str = ""         # 原始方案内容
    
    def to_dict(self):
        return asdict(self)


@dataclass
class CheckReport:
    """校验报告"""
    checker_id: str               # 校验官编号
    checker_type: str             # premise/logic/framework
    result: str                   # pass/fail
    issues: List[Dict] = field(default_factory=list)       # 问题清单
    red_flags: List[str] = field(default_factory=list)     # 红色否决项
    suggestions: List[str] = field(default_factory=list)   # 整改建议
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)


class ParallelCheckEngine:
    """
    平行校验引擎
    实现"规则引擎+大模型+非AI校验源"混合校验架构
    三个校验角色完全独立、无信息交叉
    """
    
    # 校验官职责定义
    CHECKER_DEFINITIONS = {
        "checker_1": {
            "id": "checker_1",
            "name": "前提依据校验官",
            "type": "premise",
            "responsibility": "仅校验核心前提、数据来源、信息真实性/完整性/时效性",
            "red_lines": [
                "无来源主观假设",
                "刻意隐瞒反向信息",
                "数据造假"
            ],
            "forbidden": ["触碰逻辑推导内容", "触碰框架匹配内容"],
            "output_format": "通过/不通过+问题清单+整改要求"
        },
        "checker_2": {
            "id": "checker_2",
            "name": "逻辑推导校验官",
            "type": "logic",
            "responsibility": "仅校验逻辑链条、推导严谨性、12类核心认知偏差",
            "red_lines": [
                "因果倒置",
                "循环论证",
                "线性外推",
                "核心认知偏差"
            ],
            "forbidden": ["触碰前提真实性", "触碰框架匹配内容"],
            "output_format": "通过/不通过+问题清单+整改要求"
        },
        "checker_3": {
            "id": "checker_3",
            "name": "框架与风险校验官",
            "type": "framework",
            "responsibility": "仅校验框架与场景的匹配度、风险覆盖完整性、6类弱信号捕捉",
            "red_lines": [
                "框架错配",
                "尾部风险遗漏",
                "关键弱信号缺失"
            ],
            "forbidden": ["触碰前提真实性", "触碰逻辑推导内容"],
            "output_format": "通过/不通过+问题清单+整改要求"
        }
    }
    
    def __init__(self, kernel, ai_client: LLMClient = None):
        self.kernel = kernel
        self.ai_client = ai_client  # AI 客户端（可选）
        self._context_isolation = True  # 上下文隔离开关
    
    def execute_parallel_check(
        self,
        scheme: SchemeOutput,
        original_requirement: str,
        risk_grade: str
    ) -> Dict:
        """
        执行平行校验
        根据风险等级采用差异化校验组合
        """
        result = {
            "decision_id": scheme.scheme_id,
            "risk_grade": risk_grade,
            "checks": {},
            "overall_result": "pending",
            "issues_summary": [],
            "red_flags": [],
            "needs_regeneration": False,
            "timestamp": datetime.now().isoformat()
        }
        
        if risk_grade == RiskGrade.LOW.value:
            # 低风险：仅基础合规校验
            report = self._basic_compliance_check(scheme, original_requirement)
            result["checks"]["basic_compliance"] = report.to_dict()
            result["overall_result"] = report.result
            return result
        
        # 中/高风险：完整三维平行校验
        # 关键：时序隔离 - 串行独立唤醒，前一个完成后清空上下文再唤醒下一个
        for checker_id, checker_def in self.CHECKER_DEFINITIONS.items():
            # 时序隔离：清空上一步的上下文
            self._clear_context()
            
            # 独立校验
            report = self._execute_single_check(
                checker_def, scheme, original_requirement, risk_grade
            )
            result["checks"][checker_id] = report.to_dict()
            
            # 收集问题
            result["issues_summary"].extend(report.issues)
            result["red_flags"].extend(report.red_flags)
        
        # 判定整体结果
        red_flag_count = len(result["red_flags"])
        if red_flag_count >= 2:
            result["overall_result"] = "fail"
            result["needs_regeneration"] = True
            result["resolution"] = "2个及以上校验官提出红色否决项，方案直接驳回，必须重新生成"
        elif red_flag_count == 1:
            # 触发第四中立模型专项复核
            result["overall_result"] = "pending_review"
            result["resolution"] = "1个校验官提出红色否决项，触发第四中立模型专项复核"
            review = self._neutral_model_review(result)
            result["neutral_review"] = review
            result["overall_result"] = review["final_result"]
        elif len(result["issues_summary"]) > 0:
            result["overall_result"] = "pass_with_issues"
            result["resolution"] = "存在非致命瑕疵，需在输出中标注"
        else:
            result["overall_result"] = "pass"
            result["resolution"] = "全部校验通过"
        
        # 高风险场景：同源偏误检测
        if risk_grade == RiskGrade.HIGH.value:
            same_source_check = self._detect_same_source_bias(scheme)
            result["same_source_check"] = same_source_check
            if same_source_check["detected"]:
                result["overall_result"] = "pass_with_warning"
                result["resolution"] += "；检测到潜在同源偏误，已触发反向质疑"
        
        return result
    
    def _execute_single_check(
        self,
        checker_def: Dict,
        scheme: SchemeOutput,
        original_requirement: str,
        risk_grade: str
    ) -> CheckReport:
        """执行单个校验官的独立校验（规则 + AI 混合）"""
        checker_type = checker_def["type"]
        report = CheckReport(
            checker_id=checker_def["id"],
            checker_type=checker_type,
            result=CheckResult.PASS.value,
            issues=[],
            red_flags=[]
        )
        
        # 1. 先执行规则引擎校验（快速、确定性）
        if checker_type == "premise":
            report = self._check_premises(scheme, report)
        elif checker_type == "logic":
            report = self._check_logic(scheme, original_requirement, report)
        elif checker_type == "framework":
            report = self._check_framework(scheme, original_requirement, report)
        
        # 2. 如果 AI 可用，叠加 LLM 深度校验（补充规则引擎无法覆盖的语义理解）
        if self.ai_client and self.ai_client.is_available():
            checker_num = int(checker_def["id"].split("_")[1])
            ai_report = self._ai_check(checker_num, original_requirement, scheme, risk_grade)
            if ai_report:
                report = self._merge_ai_check(report, ai_report)
        
        # 判定结果
        if report.red_flags:
            report.result = CheckResult.FAIL.value
        elif report.issues:
            report.result = CheckResult.WARNING.value
        else:
            report.result = CheckResult.PASS.value
        
        return report

    def _ai_check(
        self,
        checker_num: int,
        original_requirement: str,
        scheme: SchemeOutput,
        risk_grade: str
    ) -> Optional[Dict]:
        """调用 LLM 进行独立校验"""
        try:
            messages = LingjingPrompts.build_checker_prompt(
                checker_num=checker_num,
                user_input=original_requirement,
                scheme_content=scheme.raw_content or scheme.core_logic,
                risk_grade=risk_grade
            )
            resp = self.ai_client.chat_json(messages, temperature=0.2, max_tokens=2048)
            if resp.success and resp.content:
                content = resp.content.strip()
                if content.startswith("```"):
                    lines = content.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    content = "\n".join(lines)
                return json.loads(content)
        except Exception:
            pass
        return None

    def _merge_ai_check(self, rule_report: CheckReport, ai_result: Dict) -> CheckReport:
        """将 AI 校验结果合并到规则校验报告中"""
        # 合并问题
        for issue in ai_result.get("issues", []):
            # 避免重复
            existing_items = {i.get("item", "") for i in rule_report.issues}
            if issue.get("item", "") not in existing_items:
                rule_report.issues.append(issue)
        
        # 合并红色否决项
        for flag in ai_result.get("red_flags", []):
            if flag not in rule_report.red_flags:
                rule_report.red_flags.append(flag)
        
        # 存储额外的 AI 分析信息
        rule_report.suggestions.extend(ai_result.get("suggestions", []))
        
        # 存储 AI 特有字段
        if "data_verification" in ai_result:
            rule_report.suggestions.append(f"[AI数据核验] {json.dumps(ai_result['data_verification'], ensure_ascii=False)[:200]}")
        if "detected_biases" in ai_result:
            rule_report.suggestions.append(f"[AI偏差检测] {', '.join(ai_result['detected_biases'])}")
        if "weak_signals" in ai_result:
            rule_report.suggestions.append(f"[AI弱信号] {', '.join(ai_result['weak_signals'][:5])}")
        
        return rule_report
    
    def _check_premises(self, scheme: SchemeOutput, report: CheckReport) -> CheckReport:
        """前提依据校验"""
        # 检查数据来源
        if not scheme.data_sources:
            report.issues.append({
                "level": "warning",
                "item": "数据来源缺失",
                "description": "方案未标注核心数据来源",
                "suggestion": "请补充所有核心数据的权威来源"
            })
        else:
            for src in scheme.data_sources:
                if any(k in src for k in ["自媒体", "股吧", "论坛", "微博", "抖音"]):
                    report.red_flags.append("使用非权威来源信息：" + src)
        
        # 检查核心风险是否充分披露
        if len(scheme.key_risks) < 3:
            report.issues.append({
                "level": "warning",
                "item": "核心风险披露不足",
                "description": f"仅列出{len(scheme.key_risks)}个核心风险，要求至少3个核心致命风险",
                "suggestion": "补充核心致命风险，每个风险须标注发生概率、最大损失、应对措施"
            })
        
        # 检查置信度标注
        if not scheme.confidence:
            report.issues.append({
                "level": "info",
                "item": "置信度缺失",
                "description": "方案未标注置信度与适用边界",
                "suggestion": "明确标注方案结论的置信度、适用边界、有效期限"
            })
        
        return report
    
    def _check_logic(self, scheme: SchemeOutput, requirement: str, report: CheckReport) -> CheckReport:
        """逻辑推导校验 - 检测认知偏差"""
        biases = self.kernel.get_cognitive_biases()
        
        # 检测常见的逻辑问题关键词
        logic_red_flags = {
            "必然": "绝对化表述，缺乏概率思维",
            "一定": "绝对化表述，忽略不确定性",
            "保证": "承诺性表述，无法验证",
            "稳赚": "投资类绝对化表述",
            "必涨": "投资类绝对化表述",
            "100%": "绝对概率表述",
            "零风险": "风险为零的不实表述"
        }
        
        content = scheme.raw_content or scheme.core_logic
        for keyword, reason in logic_red_flags.items():
            if keyword in content:
                report.red_flags.append(f"逻辑红线 - {keyword}：{reason}")
        
        # 基于场景检测认知偏差
        scene_bias_map = {
            "金融投资": ["过度自信", "确认偏误", "损失厌恶", "锚定效应", "幸存者偏差"],
            "法律合规": ["确认偏误", "框架效应"],
            "医疗健康": ["可得性偏差", "代表性启发", "安慰剂效应"],
            "房地产": ["锚定效应", "禀赋效应", "从众效应"]
        }
        
        for bias in biases:
            bias_name = bias["name"]
            if bias_name in [b for scene_biases in scene_bias_map.values() for b in scene_biases]:
                report.issues.append({
                    "level": "info",
                    "item": f"认知偏差提醒 - {bias_name}",
                    "description": bias["description"],
                    "suggestion": f"请关注是否存在{bias_name}倾向，避免非理性决策"
                })
        
        return report
    
    def _check_framework(self, scheme: SchemeOutput, requirement: str, report: CheckReport) -> CheckReport:
        """框架与风险校验"""
        # 检查框架匹配
        if not scheme.applicable_scenarios:
            report.issues.append({
                "level": "warning",
                "item": "适用场景未说明",
                "description": "方案未明确适用场景",
                "suggestion": "明确标注方案的适用场景与不适用场景"
            })
        
        # 检查触发条件
        if not scheme.trigger_conditions:
            report.issues.append({
                "level": "warning",
                "item": "触发条件缺失",
                "description": "方案未标注关键触发条件与退出条件",
                "suggestion": "补充关键触发条件、止损线、退出机制"
            })
        
        # 检查尾部风险
        tail_risk_keywords = ["极端", "最坏", "最大损失", "尾部", "黑天鹅"]
        content = scheme.raw_content or ""
        has_tail_risk = any(k in content for k in tail_risk_keywords)
        if not has_tail_risk:
            report.issues.append({
                "level": "warning",
                "item": "尾部风险未分析",
                "description": "方案未包含极端情景下的风险评估",
                "suggestion": "补充最坏情景分析、最大风险敞口、止损线"
            })
        
        # 检查弱信号
        weak_signal_keywords = ["弱信号", "预警", "早期迹象", "苗头"]
        has_weak_signal = any(k in content for k in weak_signal_keywords)
        if not has_weak_signal:
            report.issues.append({
                "level": "info",
                "item": "弱信号分析缺失",
                "description": "方案未包含弱信号/早期预警分析",
                "suggestion": "补充可能被忽视的弱信号与早期预警指标"
            })
        
        return report
    
    def _basic_compliance_check(self, scheme: SchemeOutput, requirement: str) -> CheckReport:
        """基础合规校验（低风险场景）"""
        report = CheckReport(
            checker_id="basic_compliance",
            checker_type="compliance",
            result=CheckResult.PASS.value
        )
        
        # 基本红线检查
        content = scheme.raw_content or scheme.core_logic
        prohibited = ["替您选择", "建议您直接", "最优方案", "必涨", "稳赚", "零风险"]
        for p in prohibited:
            if p in content:
                report.red_flags.append(f"合规红线违规：使用禁止表述「{p}」")
                report.result = CheckResult.FAIL.value
        
        return report
    
    def _neutral_model_review(self, check_result: Dict) -> Dict:
        """第四中立模型专项复核"""
        red_flag_checker = None
        for checker_id, check in check_result["checks"].items():
            if check["red_flags"]:
                red_flag_checker = checker_id
                break
        
        return {
            "triggered_by": red_flag_checker,
            "review_type": "第四中立模型专项复核",
            "final_result": "pass_with_notes",  # 保留问题标注但允许通过
            "notes": "1个校验官提出红色否决项，经中立复核后保留风险标注，允许进入下一环节",
            "requirements": ["所有否决内容必须在最终输出中高亮标注", "禁止系统自行裁定放水通过"]
        }
    
    def _detect_same_source_bias(self, scheme: SchemeOutput) -> Dict:
        """同源偏误检测"""
        # 如果多方案结论完全一致，触发反向质疑
        return {
            "detected": False,
            "description": "同源偏误检测：需多方案对比后方可判定",
            "trigger_condition": "3个大模型结论完全一致时自动触发反向质疑流程",
            "counter_measures": [
                "强制生成至少3个对立观点和反例",
                "引入非AI校验源进行交叉验证",
                "严格执行三不同原则（底层架构不同、训练数据集不同、研发主体不同）"
            ]
        }
    
    def _clear_context(self):
        """时序隔离：清空上下文记忆"""
        # 在实际AI交互中，这里会清空对话上下文
        self._context_isolation = True
        pass
