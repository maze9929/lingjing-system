# 元监与全链路追溯模块 (Module 3)
# 全流程安全守门员

import json
import uuid
import hashlib
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from core.kernel import RiskGrade


@dataclass
class MetaMonitorReport:
    """元监报告"""
    monitor_id: str
    decision_id: str
    process_compliance: Dict = field(default_factory=dict)    # 执行标尺结果
    framework_compliance: Dict = field(default_factory=dict)   # 体系标尺结果
    overall_result: str = "pass"                               # pass/fail/intercept
    interventions: List[Dict] = field(default_factory=list)    # 干预记录
    data_verification: List[Dict] = field(default_factory=list) # 数据核验结果
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)


@dataclass
class DecisionLedger:
    """决策辅助台账 - 不可篡改的全流程记录"""
    ledger_id: str
    decision_id: str
    user_id: str
    risk_grade: str
    requirement_summary: str = ""
    risk_grading_detail: Dict = field(default_factory=dict)
    schemes: List[Dict] = field(default_factory=list)
    parallel_check_reports: Dict = field(default_factory=dict)
    meta_monitor_report: Dict = field(default_factory=dict)
    risk_warnings: List[str] = field(default_factory=list)
    cognitive_bias_alerts: List[str] = field(default_factory=list)
    user_decision: str = ""
    user_confirmation: bool = False
    content_hash: str = ""        # 内容哈希（防篡改）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    archived: bool = False
    
    def to_dict(self):
        return asdict(self)
    
    def compute_hash(self) -> str:
        """计算台账内容哈希"""
        content = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


class MetaMonitor:
    """
    双标尺元监体系
    执行标尺：监查流程合规性
    体系标尺：监查框架与场景匹配度
    """
    
    def __init__(self, kernel, ledger_dir: str):
        self.kernel = kernel
        self.ledger_dir = ledger_dir
        os.makedirs(ledger_dir, exist_ok=True)
    
    def execute_monitor(
        self,
        decision_id: str,
        risk_grade: str,
        requirement: str,
        scheme_outputs: List,
        check_result: Dict,
        user_id: str = "anonymous"
    ) -> MetaMonitorReport:
        """执行全流程元监监查"""
        report = MetaMonitorReport(
            monitor_id=f"MM-{uuid.uuid4().hex[:8].upper()}",
            decision_id=decision_id
        )
        
        # === 执行标尺：流程合规性监查 ===
        report.process_compliance = self._check_process_compliance(
            risk_grade, check_result
        )
        
        # === 体系标尺：框架与场景匹配度监查 ===
        report.framework_compliance = self._check_framework_match(
            requirement, scheme_outputs
        )
        
        # === 数据真实性核验 ===
        report.data_verification = self._verify_data_sources(scheme_outputs)
        
        # === 整体判定 ===
        process_ok = report.process_compliance.get("result") == "pass"
        framework_ok = report.framework_compliance.get("result") == "pass"
        data_ok = all(d.get("verified", False) for d in report.data_verification)
        
        if not process_ok or not framework_ok:
            report.overall_result = "intercept"
            report.interventions.append({
                "type": "流程拦截",
                "reason": "流程合规性或框架匹配度检查未通过",
                "action": "要求重新生成方案",
                "timestamp": datetime.now().isoformat()
            })
        elif not data_ok:
            report.overall_result = "pass_with_warnings"
        else:
            report.overall_result = "pass"
        
        return report
    
    def _check_process_compliance(self, risk_grade: str, check_result: Dict) -> Dict:
        """执行标尺 - 流程合规性监查"""
        issues = []
        
        # 检查是否按风险等级执行对应流程
        expected_checks = {
            RiskGrade.LOW.value: ["basic_compliance"],
            RiskGrade.MEDIUM.value: ["checker_1", "checker_2", "checker_3"],
            RiskGrade.HIGH.value: ["checker_1", "checker_2", "checker_3"]
        }
        
        expected = expected_checks.get(risk_grade, [])
        actual = list(check_result.get("checks", {}).keys())
        
        missing = set(expected) - set(actual)
        if missing:
            issues.append({
                "level": "fatal",
                "item": "校验环节缺失",
                "description": f"缺少必要的校验环节：{missing}",
                "required_action": "补充缺失的校验环节"
            })
        
        # 检查是否有红色否决项被放水通过
        if check_result.get("red_flags"):
            if check_result.get("overall_result") == "pass":
                issues.append({
                    "level": "fatal",
                    "item": "红色否决项被放水通过",
                    "description": "存在红色否决项但整体结果为通过",
                    "required_action": "必须重新处理红色否决项"
                })
        
        return {
            "result": "fail" if any(i["level"] == "fatal" for i in issues) else "pass",
            "risk_grade": risk_grade,
            "expected_checks": expected,
            "actual_checks": actual,
            "issues": issues
        }
    
    def _check_framework_match(self, requirement: str, schemes: List) -> Dict:
        """体系标尺 - 框架与场景匹配度监查"""
        issues = []
        
        # 检查方案数量（中/高风险应有多方案）
        if len(schemes) < 1:
            issues.append({
                "level": "fatal",
                "item": "方案缺失",
                "description": "未生成任何决策方案",
                "required_action": "必须生成至少1个决策方案"
            })
        
        # 检查多方案均衡性
        if len(schemes) > 1:
            lengths = [len(s.raw_content or s.core_logic or "") for s in schemes]
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                for i, length in enumerate(lengths):
                    if length < avg_len * 0.8:
                        issues.append({
                            "level": "warning",
                            "item": f"方案{i+1}内容过于简略",
                            "description": f"方案{i+1}字数({length})低于平均值({avg_len:.0f})的80%，存在隐性倾向性",
                            "required_action": "确保各方案内容详略均衡，差异控制在±20%以内"
                        })
                        break
        
        return {
            "result": "fail" if any(i["level"] == "fatal" for i in issues) else 
                     "pass_with_warnings" if any(i["level"] == "warning" for i in issues) else "pass",
            "scheme_count": len(schemes),
            "issues": issues
        }
    
    def _verify_data_sources(self, schemes: List) -> List[Dict]:
        """数据来源核验"""
        verifications = []
        
        # 权威数据源白名单
        authoritative_sources = [
            "国家统计局", "央行", "证监会", "交易所", "上市公司公告",
            "中国人大网", "最高法官网", "国家卫健委", "国家药监局",
            "中华医学会", "住建局", "自然资源局", "权威金融数据库",
            "权威法律法规数据库", "权威医学期刊"
        ]
        
        for scheme in schemes:
            if hasattr(scheme, 'data_sources'):
                for src in scheme.data_sources:
                    is_authoritative = any(a in src for a in authoritative_sources)
                    verifications.append({
                        "source": src,
                        "verified": is_authoritative,
                        "authority_level": "权威" if is_authoritative else "非权威",
                        "note": "已通过权威数据源核验" if is_authoritative else "非权威来源，不可作为核心前提"
                    })
        
        if not verifications:
            verifications.append({
                "source": "无",
                "verified": False,
                "authority_level": "未知",
                "note": "方案未标注数据来源，建议补充"
            })
        
        return verifications
    
    def generate_ledger(
        self,
        decision_id: str,
        user_id: str,
        risk_grade: str,
        requirement_summary: str,
        risk_grading_detail: Dict,
        schemes: List,
        check_result: Dict,
        monitor_report: MetaMonitorReport,
        risk_warnings: List[str] = None,
        cognitive_bias_alerts: List[str] = None
    ) -> DecisionLedger:
        """生成不可篡改的决策辅助台账"""
        ledger = DecisionLedger(
            ledger_id=f"LDG-{uuid.uuid4().hex[:12].upper()}",
            decision_id=decision_id,
            user_id=user_id,
            risk_grade=risk_grade,
            requirement_summary=requirement_summary,
            risk_grading_detail=risk_grading_detail,
            schemes=[s.to_dict() if hasattr(s, 'to_dict') else s for s in schemes],
            parallel_check_reports=check_result,
            meta_monitor_report=monitor_report.to_dict(),
            risk_warnings=risk_warnings or [],
            cognitive_bias_alerts=cognitive_bias_alerts or []
        )
        
        # 计算内容哈希
        ledger.content_hash = ledger.compute_hash()
        
        # 保存台账
        self._save_ledger(ledger)
        
        return ledger
    
    def _save_ledger(self, ledger: DecisionLedger):
        """保存台账到文件"""
        filepath = os.path.join(
            self.ledger_dir,
            f"{ledger.ledger_id}.json"
        )
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(ledger.to_dict(), f, ensure_ascii=False, indent=2)
    
    def verify_ledger_integrity(self, ledger_id: str) -> Dict:
        """验证台账完整性（防篡改）"""
        filepath = os.path.join(self.ledger_dir, f"{ledger_id}.json")
        if not os.path.exists(filepath):
            return {"valid": False, "reason": "台账文件不存在"}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        stored_hash = data.get("content_hash", "")
        # 重新计算哈希（排除原哈希值）
        temp_data = {k: v for k, v in data.items() if k != "content_hash"}
        computed_hash = hashlib.sha256(
            json.dumps(temp_data, sort_keys=True, ensure_ascii=False).encode('utf-8')
        ).hexdigest()
        
        return {
            "valid": stored_hash == computed_hash,
            "stored_hash": stored_hash,
            "reason": "台账完整，未被篡改" if stored_hash == computed_hash else "台账已被篡改！内容哈希不匹配"
        }
