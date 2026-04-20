# AI 方案生成模块
# 用大模型生成真正有深度的决策辅助方案

import json
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

from core.parallel_check import SchemeOutput
from core.ai_client import LLMClient, LingjingPrompts, LLMMessage
from core.requirement_parser import DecisionRequirement


class AISchemeGenerator:
    """
    AI 方案生成器
    - 根据风险等级生成不同数量和深度的方案
    - 每个方案由 LLM 独立生成（时序隔离）
    - 高风险：乐观/中性/悲观三方案
    - 中风险：保守/稳健/进取三方案
    - 低风险：单一中性方案
    """

    def __init__(self, ai_client: LLMClient):
        self.ai_client = ai_client

    def is_available(self) -> bool:
        return self.ai_client and self.ai_client.is_available()

    def generate_schemes(
        self,
        requirement: DecisionRequirement,
        risk_grade: str,
        user_input: str
    ) -> List[SchemeOutput]:
        """
        生成决策方案
        
        Returns:
            SchemeOutput 列表
        """
        if not self.is_available():
            return self._template_generation(requirement, risk_grade)

        decision_id = requirement.decision_id
        ai_analysis = requirement.additional_info.get("ai_analysis", {})

        if risk_grade == "low":
            # 低风险：单一方案，简洁
            scheme = self._generate_single_scheme(
                decision_id, user_input, ai_analysis, risk_grade,
                "neutral", "中性分析"
            )
            return [scheme] if scheme else [self._make_template_scheme(
                decision_id, "neutral", "中性分析", requirement, risk_grade
            )]

        elif risk_grade == "medium":
            # 中风险：三方案
            types = [
                ("conservative", "保守方案"),
                ("balanced", "稳健方案"),
                ("aggressive", "进取方案")
            ]
        else:
            # 高风险：三方案全景
            types = [
                ("optimistic", "乐观方案"),
                ("neutral", "中性方案"),
                ("pessimistic", "悲观方案")
            ]

        schemes = []
        for stype, label in types:
            if self.is_available():
                scheme = self._generate_single_scheme(
                    decision_id, user_input, ai_analysis, risk_grade, stype, label
                )
                if scheme:
                    schemes.append(scheme)
                else:
                    schemes.append(self._make_template_scheme(
                        decision_id, stype, label, requirement, risk_grade
                    ))
            else:
                # 无 AI 时也生成多方案（用模板）
                schemes.append(self._make_template_scheme(
                    decision_id, stype, label, requirement, risk_grade
                ))

        return schemes

    def _generate_single_scheme(
        self,
        decision_id: str,
        user_input: str,
        ai_analysis: Dict,
        risk_grade: str,
        scheme_type: str,
        scheme_label: str
    ) -> Optional[SchemeOutput]:
        """用 LLM 生成单个方案"""
        messages = LingjingPrompts.build_scheme_generation(
            user_input=user_input,
            requirement_analysis=ai_analysis,
            risk_grade=risk_grade,
            scheme_type=scheme_type,
            scheme_label=scheme_label
        )

        resp = self.ai_client.chat(messages, temperature=0.7, max_tokens=4096)
        if not resp.success or not resp.content.strip():
            return None

        content = resp.content.strip()

        # 从 LLM 输出中提取结构化信息（尽力而为）
        scheme = SchemeOutput(
            scheme_id=f"SCH-{decision_id}-{scheme_type[:3].upper()}",
            scheme_type=scheme_type,
            core_logic=self._extract_section(content, "核心逻辑"),
            expected_return=self._extract_section(content, "收益预期"),
            risk_exposure=self._extract_section(content, "风险敞口分析"),
            applicable_scenarios=self._extract_section(content, "适用场景"),
            trigger_conditions=self._extract_section(content, "触发条件"),
            key_risks=self._extract_risks(content),
            data_sources=self._extract_sources(content),
            confidence=self._extract_confidence(content),
            raw_content=content
        )

        return scheme

    def _extract_section(self, content: str, section_name: str) -> str:
        """从 Markdown 中提取指定章节内容"""
        import re
        # 匹配 ## 或 ### 后跟章节名
        pattern = rf'#{1,3}\s*.*?{section_name}[：:]?\s*\n(.*?)(?=\n#{1,3}\s|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            text = match.group(1).strip()
            # 去掉子标题行
            lines = [l for l in text.split("\n") if not l.strip().startswith("#")]
            return "\n".join(lines)[:500]
        return ""

    def _extract_risks(self, content: str) -> List[str]:
        """提取风险列表"""
        risks = []
        lines = content.split("\n")
        in_risk_section = False
        for line in lines:
            if "风险" in line and ("致命" in line or "次要" in line or "核心" in line):
                in_risk_section = True
                continue
            if in_risk_section:
                if line.strip().startswith("#") or line.strip() == "":
                    if risks:  # 已收集到风险则停止
                        break
                    continue
                if line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "- ", "* ")):
                    # 清理序号
                    clean = line.strip().lstrip("0123456789.-* ")
                    if clean and len(clean) > 5:
                        risks.append(clean[:100])
        return risks if risks else ["详见方案完整内容"]

    def _extract_sources(self, content: str) -> List[str]:
        """提取数据来源"""
        sources = []
        lines = content.split("\n")
        in_source_section = False
        for line in lines:
            if "数据来源" in line:
                in_source_section = True
                continue
            if in_source_section:
                if line.strip().startswith("#") and "数据来源" not in line:
                    break
                if line.strip().startswith(("1.", "2.", "3.", "- ", "* ")):
                    sources.append(line.strip().lstrip("0123456789.-* ")[:100])
        return sources if sources else ["AI分析生成，建议通过权威渠道核验"]

    def _extract_confidence(self, content: str) -> str:
        """提取置信度说明"""
        if "置信度" in content:
            import re
            match = re.search(r'置信度[：:：]?\s*(.*?)(?:\n|$)', content)
            if match:
                return match.group(1).strip()[:100]
        return "中等置信度，建议结合更多信息验证"

    def _make_template_scheme(
        self, decision_id: str, scheme_type: str, label: str,
        requirement: DecisionRequirement, risk_grade: str
    ) -> SchemeOutput:
        """模板兜底方案（AI 不可用时）"""
        return SchemeOutput(
            scheme_id=f"SCH-{decision_id}-{scheme_type[:3].upper()}",
            scheme_type=scheme_type,
            core_logic=f"{label}：基于需求「{requirement.decision_goal}」的{scheme_type}策略分析",
            expected_return=f"{scheme_type}情景预期收益",
            risk_exposure=f"{scheme_type}情景风险敞口",
            applicable_scenarios=f"{scheme_type}偏好场景",
            trigger_conditions="关键触发条件与止损线（AI深度分析不可用，请结合专业意见）",
            key_risks=[
                "核心前提失效可能导致重大损失",
                "外部环境变化的黑天鹅风险",
                "执行偏差风险",
                "信息不对称风险"
            ],
            data_sources=["AI分析不可用，建议通过权威渠道获取信息"],
            confidence="置信度未知，AI深度分析当前不可用",
            raw_content=f"{label}（模板兜底）：AI 大模型当前不可用，本方案为模板生成。建议配置 AI API Key 后重新生成以获取深度分析。"
        )

    def _template_generation(
        self, requirement: DecisionRequirement, risk_grade: str
    ) -> List[SchemeOutput]:
        """模板生成（无 AI 时）"""
        decision_id = requirement.decision_id

        if risk_grade == "low":
            return [self._make_template_scheme(
                decision_id, "neutral", "中性分析", requirement, risk_grade
            )]

        elif risk_grade == "medium":
            types = [
                ("conservative", "保守方案"),
                ("balanced", "稳健方案"),
                ("aggressive", "进取方案")
            ]
        else:
            types = [
                ("optimistic", "乐观方案"),
                ("neutral", "中性方案"),
                ("pessimistic", "悲观方案")
            ]

        return [self._make_template_scheme(decision_id, stype, label, requirement, risk_grade)
                for stype, label in types]
