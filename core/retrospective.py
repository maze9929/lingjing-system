# 复盘与双轨迭代优化模块 (Module 5)
# 永续迭代、越用越准的核心载体

import json
import os
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from core.kernel import GradientKernel


@dataclass
class RetrospectiveRecord:
    """复盘记录"""
    review_id: str
    decision_id: str
    user_id: str
    actual_result: str = ""              # 实际结果
    predicted_result: str = ""           # 预判结果
    deviation_analysis: str = ""         # 偏差分析
    error_root_cause: str = ""           # 误差根因
    success_factors: List[str] = field(default_factory=list)  # 成功经验
    defect_list: List[str] = field(default_factory=list)      # 缺陷清单
    optimization_suggestions: List[str] = field(default_factory=list)  # 优化建议
    
    # 量化评估指标
    decision_accuracy: float = 0.0      # 决策准确率
    risk_avoidance_rate: float = 0.0    # 风险规避率
    relative_error: float = 0.0         # 相对误差率
    review_optimization_rate: float = 0.0  # 复盘优化率
    cognitive_bias_identified: bool = False  # 是否识别认知偏差
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)


@dataclass
class PersonalizedRule:
    """用户个性化规则"""
    rule_id: str
    user_id: str
    rule_content: str
    scenario: str                       # 适用场景
    backtest_result: str = ""           # 回测结果
    user_confirmed: bool = False        # 用户确认
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)


class RetrospectiveEngine:
    """
    双轨制迭代引擎
    个性化迭代 + 通用规则迭代
    """
    
    def __init__(self, kernel: GradientKernel, case_dir: str):
        self.kernel = kernel
        self.case_dir = case_dir
        os.makedirs(case_dir, exist_ok=True)
    
    def create_review(
        self,
        decision_id: str,
        user_id: str,
        actual_result: str,
        predicted_result: str,
        deviation_analysis: str = "",
        error_root_cause: str = "",
        success_factors: List[str] = None,
        defect_list: List[str] = None,
        optimization_suggestions: List[str] = None
    ) -> RetrospectiveRecord:
        """创建复盘记录"""
        review = RetrospectiveRecord(
            review_id=f"REV-{uuid.uuid4().hex[:8].upper()}",
            decision_id=decision_id,
            user_id=user_id,
            actual_result=actual_result,
            predicted_result=predicted_result,
            deviation_analysis=deviation_analysis,
            error_root_cause=error_root_cause,
            success_factors=success_factors or [],
            defect_list=defect_list or [],
            optimization_suggestions=optimization_suggestions or []
        )
        
        # 计算量化评估指标
        review = self._compute_metrics(review)
        
        # 保存复盘记录
        self._save_review(review)
        
        # 沉淀到案例库
        self._archive_to_case_library(review)
        
        return review
    
    def _compute_metrics(self, review: RetrospectiveRecord) -> RetrospectiveRecord:
        """计算决策辅助效果量化指标"""
        # 决策准确率（简化计算）
        if review.predicted_result and review.actual_result:
            # 基于关键词匹配简化判断
            pred_keywords = set(review.predicted_result.split())
            actual_keywords = set(review.actual_result.split())
            overlap = pred_keywords & actual_keywords
            review.decision_accuracy = len(overlap) / max(len(pred_keywords), 1) * 100
        
        # 相对误差率（如有数值型结果）
        try:
            pred_val = float(''.join(c for c in review.predicted_result if c.isdigit() or c == '.') or '0')
            actual_val = float(''.join(c for c in review.actual_result if c.isdigit() or c == '.') or '0')
            if pred_val != 0:
                review.relative_error = abs(actual_val - pred_val) / abs(pred_val) * 100
        except (ValueError, ZeroDivisionError):
            review.relative_error = 0
        
        # 复盘优化率
        if review.defect_list:
            optimized = sum(1 for d in review.defect_list if any(d in s for s in review.optimization_suggestions))
            review.review_optimization_rate = optimized / len(review.defect_list) * 100 if review.defect_list else 100
        
        return review
    
    def _save_review(self, review: RetrospectiveRecord):
        """保存复盘记录"""
        filepath = os.path.join(self.case_dir, "reviews", f"{review.review_id}.json")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(review.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _archive_to_case_library(self, review: RetrospectiveRecord):
        """归档到案例库"""
        # 确定案例分类
        case_type = "标杆案例"
        if review.defect_list:
            case_type = "缺陷案例" if review.relative_error > 30 else "边界案例"
        
        case = {
            "case_id": f"CASE-{uuid.uuid4().hex[:8].upper()}",
            "decision_id": review.decision_id,
            "user_id": review.user_id,
            "case_type": case_type,
            "actual_result": review.actual_result,
            "predicted_result": review.predicted_result,
            "deviation_analysis": review.deviation_analysis,
            "defect_list": review.defect_list,
            "optimization_suggestions": review.optimization_suggestions,
            "metrics": {
                "accuracy": review.decision_accuracy,
                "error_rate": review.relative_error
            },
            "timestamp": review.timestamp
        }
        
        filepath = os.path.join(self.case_dir, f"{case_type}_{case['case_id']}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(case, f, ensure_ascii=False, indent=2)
    
    def get_user_review_history(self, user_id: str) -> List[Dict]:
        """获取用户复盘历史"""
        reviews_dir = os.path.join(self.case_dir, "reviews")
        if not os.path.exists(reviews_dir):
            return []
        
        history = []
        for filename in os.listdir(reviews_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(reviews_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("user_id") == user_id:
                        history.append(data)
        
        return sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    def get_similar_cases(self, industry: str, risk_grade: str, limit: int = 5) -> List[Dict]:
        """获取同场景历史案例"""
        cases = []
        if not os.path.exists(self.case_dir):
            return cases
        
        for filename in os.listdir(self.case_dir):
            if filename.endswith('.json') and filename.startswith("CASE"):
                filepath = os.path.join(self.case_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    case = json.load(f)
                    cases.append(case)
        
        # 优先返回缺陷案例
        defect_cases = [c for c in cases if c.get("case_type") == "缺陷案例"]
        other_cases = [c for c in cases if c.get("case_type") != "缺陷案例"]
        
        return (defect_cases + other_cases)[:limit]
    
    def evaluate_system_performance(self, user_id: str = None) -> Dict:
        """评估系统决策辅助效果"""
        history = self.get_user_review_history(user_id) if user_id else []
        
        if not history:
            return {
                "total_decisions": 0,
                "average_accuracy": 0,
                "average_error_rate": 0,
                "optimization_rate": 0,
                "trend": "insufficient_data"
            }
        
        accuracies = [h.get("metrics", {}).get("accuracy", 0) for h in history]
        errors = [h.get("metrics", {}).get("error_rate", 0) for h in history]
        
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
        avg_error = sum(errors) / len(errors) if errors else 0
        
        # 判断趋势
        if len(accuracies) >= 3:
            recent = sum(accuracies[-3:]) / 3
            earlier = sum(accuracies[:-3]) / len(accuracies[:-3]) if len(accuracies) > 3 else avg_accuracy
            trend = "improving" if recent > earlier else "stable"
        else:
            trend = "insufficient_data"
        
        # 触发优化闭环的规则检查
        optimization_needed = []
        if avg_accuracy < 60:
            optimization_needed.append("月度决策准确率低于60%，建议立即触发系统规则专项优化")
        if avg_error > 30:
            optimization_needed.append("相对误差率高于30%，建议优化核心分析模型")
        
        return {
            "total_decisions": len(history),
            "average_accuracy": round(avg_accuracy, 2),
            "average_error_rate": round(avg_error, 2),
            "trend": trend,
            "optimization_needed": optimization_needed,
            "recommendation": "持续完成决策复盘，系统将不断优化适配您的决策习惯" if trend == "improving" else "建议增加复盘频率，帮助系统更好地适配您的需求"
        }
