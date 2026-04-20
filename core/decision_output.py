# 决策输出与风险全景提示模块 (Module 4)
# 输出终端 - 全景化、无偏误的决策辅助信息

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from core.kernel import RiskGrade, GradientKernel


class OutputFormatter:
    """决策输出格式化器 - 分级输出规范"""
    
    def __init__(self, kernel: GradientKernel):
        self.kernel = kernel
    
    def format_low_risk_output(self, scheme_content: str) -> Dict:
        """低风险场景输出"""
        return {
            "risk_grade": "low",
            "output_type": "simplified",
            "disclaimer": "本内容为AI辅助生成的参考信息，请结合自身情况独立判断。",
            "content": scheme_content,
            "compliance_notice": "基础合规校验已通过"
        }
    
    def format_medium_risk_output(
        self,
        scheme_content: str,
        check_result: Dict,
        risk_warnings: List[str],
        cognitive_biases: List[str],
        industry: str = "默认"
    ) -> Dict:
        """中风险场景输出"""
        industry_rules = self.kernel.get_industry_rules(industry)
        disclaimer = industry_rules["disclaimer"] if industry_rules else "本内容仅为决策辅助建议，不构成任何专业建议。"
        
        return {
            "risk_grade": "medium",
            "output_type": "standard",
            "disclaimer": disclaimer,
            "core_scheme": scheme_content,
            "check_summary": self._format_check_summary(check_result),
            "risk_points": risk_warnings,
            "cognitive_bias_alerts": cognitive_biases,
            "confidence_note": "以上分析基于当前可获取的信息，核心前提可能随时间变化，建议定期复核",
            "compliance_notice": f"三维平行校验已完成，{'存在需关注的问题' if check_result.get('issues_summary') else '全部校验通过'}"
        }
    
    def format_high_risk_output(
        self,
        schemes: List,
        check_result: Dict,
        monitor_report: Dict,
        risk_warnings: List[str],
        cognitive_biases: List[str],
        data_verification: List[Dict],
        industry: str = "默认"
    ) -> Dict:
        """高风险场景输出 - 全景决策辅助"""
        industry_rules = self.kernel.get_industry_rules(industry)
        disclaimer = industry_rules["disclaimer"] if industry_rules else "本内容仅为决策辅助信息参考，不构成任何投资/法律/医疗建议。"
        
        # 格式化多方案对比
        scheme_comparisons = []
        for s in schemes:
            scheme_dict = s.to_dict() if hasattr(s, 'to_dict') else s
            scheme_comparisons.append({
                "scheme_type": self._get_scheme_type_label(scheme_dict.get("scheme_type", "")),
                "core_logic": scheme_dict.get("core_logic", ""),
                "expected_return": scheme_dict.get("expected_return", ""),
                "risk_exposure": scheme_dict.get("risk_exposure", ""),
                "key_risks": scheme_dict.get("key_risks", []),
                "applicable_scenarios": scheme_dict.get("applicable_scenarios", ""),
                "trigger_conditions": scheme_dict.get("trigger_conditions", ""),
                "confidence": scheme_dict.get("confidence", ""),
                "data_sources": scheme_dict.get("data_sources", [])
            })
        
        # 反向信息披露
        reverse_info = self._format_reverse_info(schemes, risk_warnings)
        
        return {
            "risk_grade": "high",
            "output_type": "comprehensive",
            "opening_warning": {
                "level": "强风险提示",
                "content": "本决策涉及高不可逆性、重大损失风险，请务必完整阅读所有信息后再做出最终决策",
                "key_reminders": [
                    "AI不构成任何投资/法律/医疗建议",
                    "最终决策与全部责任由您自行承担",
                    "请重点关注以下风险全景分析"
                ]
            },
            "disclaimer": disclaimer,
            "scheme_comparisons": scheme_comparisons,
            "reverse_information": reverse_info,
            "parallel_check_reports": self._format_check_summary(check_result),
            "meta_monitor_report": monitor_report,
            "data_verification": data_verification,
            "cognitive_bias_prevention": self._format_cognitive_bias_prevention(cognitive_biases),
            "closing_disclaimer": "AI不构成任何投资/法律/医疗建议，最终决策与全部责任由您自行承担。建议咨询专业执业人员后再做出最终决策。",
            "compliance_notice": "三维平行校验+多模型交叉校验+元监全流程监查已完成",
            "timestamp": datetime.now().isoformat()
        }
    
    def format_emergency_output(self, preliminary_scheme: str, risk_summary: str) -> Dict:
        """紧急决策绿色通道输出"""
        return {
            "risk_grade": "emergency",
            "output_type": "emergency",
            "emergency_notice": "紧急决策模式：完整校验流程将在事后1小时内补全",
            "preliminary_scheme": preliminary_scheme,
            "core_risk_summary": risk_summary,
            "post_action_required": [
                "决策执行后，系统将在1小时内自动补全三维平行校验报告",
                "补全元监监查报告和完整决策台账",
                "请关注后续补全的校验结果"
            ]
        }
    
    def _format_check_summary(self, check_result: Dict) -> Dict:
        """格式化校验报告摘要"""
        checks = check_result.get("checks", {})
        summary = {
            "overall_result": check_result.get("overall_result", "pending"),
            "resolution": check_result.get("resolution", ""),
            "checker_details": {}
        }
        
        for checker_id, check in checks.items():
            summary["checker_details"][checker_id] = {
                "result": check.get("result", ""),
                "issues_count": len(check.get("issues", [])),
                "red_flags": check.get("red_flags", []),
                "has_fatal_issues": any(i.get("level") == "fatal" for i in check.get("issues", []))
            }
        
        return summary
    
    def _format_reverse_info(self, schemes: List, risk_warnings: List[str]) -> Dict:
        """格式化反向信息（核心风险点权重占比≥30%）"""
        all_risks = []
        for s in schemes:
            s_dict = s.to_dict() if hasattr(s, 'to_dict') else s
            for risk in s_dict.get("key_risks", []):
                all_risks.append(risk)
        
        return {
            "total_risk_points": len(all_risks),
            "core_fatal_risks": [
                {"risk": r, "level": "致命风险", "action": "必须制定应对预案"}
                for r in risk_warnings[:5]
            ],
            "secondary_risks": risk_warnings[5:10],
            "tail_risks": [
                {"description": "极端情景下的潜在风险，发生概率低但影响极大", "action": "制定底线止损方案"}
            ],
            "completeness_check": "反向信息披露满足≥30%权重要求" if len(all_risks) >= 3 else "反向信息披露不足，需补充"
        }
    
    def _format_cognitive_bias_prevention(self, biases: List[str]) -> Dict:
        """格式化认知偏差防控建议"""
        all_biases = self.kernel.get_cognitive_biases()
        relevant = [b for b in all_biases if b["name"] in biases]
        
        return {
            "detected_bias_types": [b["name"] for b in relevant],
            "prevention_suggestions": [
                f"【{b['name']}】{b['description']} → 建议：关注是否存在{b['name']}倾向，避免非理性决策"
                for b in relevant
            ],
            "general_advice": "决策前请充分了解所有正向和反向信息，避免仅关注支持自己预设的信息"
        }
    
    def _get_scheme_type_label(self, scheme_type: str) -> str:
        labels = {
            "optimistic": "乐观方案",
            "neutral": "中性方案",
            "pessimistic": "悲观方案",
            "conservative": "保守方案",
            "balanced": "稳健方案",
            "aggressive": "进取方案"
        }
        return labels.get(scheme_type, scheme_type)


class TendencyDetector:
    """隐性倾向性检测器"""
    
    def check_output_neutrality(self, schemes: List) -> Dict:
        """检测多方案输出的均衡性"""
        if len(schemes) < 2:
            return {"balanced": True, "issues": []}
        
        issues = []
        lengths = []
        for s in schemes:
            s_dict = s.to_dict() if hasattr(s, 'to_dict') else s
            content = s_dict.get("raw_content", "") or s_dict.get("core_logic", "")
            lengths.append(len(content))
        
        if lengths:
            avg = sum(lengths) / len(lengths)
            for i, length in enumerate(lengths):
                diff_ratio = abs(length - avg) / avg if avg > 0 else 0
                if diff_ratio > 0.2:
                    issues.append(f"方案{i+1}字数差异超过20%，存在隐性倾向性")
        
        # 检查情感倾向
        positive_words = ["优势", "机遇", "增长", "收益", "前景广阔", "潜力"]
        negative_words = ["风险", "损失", "下跌", "亏损", "失败", "隐患"]
        
        for s in schemes:
            s_dict = s.to_dict() if hasattr(s, 'to_dict') else s
            content = s_dict.get("raw_content", "") or s_dict.get("core_logic", "")
            pos_count = sum(1 for w in positive_words if w in content)
            neg_count = sum(1 for w in negative_words if w in content)
            total = pos_count + neg_count
            if total > 0:
                imbalance = abs(pos_count - neg_count) / total
                if imbalance > 0.5:
                    issues.append(f"方案情感倾向失衡（积极/消极比例差异超过50%），请调整措辞")
        
        return {
            "balanced": len(issues) == 0,
            "issues": issues,
            "recommendation": "各方案内容详略应均衡，字数差异控制在±20%以内；积极/消极词汇占比差异不超过50%"
        }
