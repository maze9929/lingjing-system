# 梯度式内核层 - 系统核心骨架
# 第0层：全体系唯一复用根基

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import time
import uuid


class RedLineLevel(Enum):
    """红线违规等级"""
    NONE = "none"
    LIGHT = "light"       # 轻度违规：单次非核心红线
    MEDIUM = "medium"     # 中度违规：核心红线或累计2次轻度
    SEVERE = "severe"     # 重度违规：累计3次及以上核心红线


class RiskGrade(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EMERGENCY = "emergency"


class KernelLayer(Enum):
    """内核梯度层"""
    ABSOLUTE = "absolute"     # 绝对不可变层（硬编码锁定）
    SEMI_FIXED = "semi_fixed" # 半固定规则层（季度可迭代）
    DYNAMIC = "dynamic"       # 动态适配层（月度可更新）


# ============================================================
# 绝对不可变层 - 6条底层设计红线（永久固定，不可修改）
# ============================================================

ABSOLUTE_RED_LINES = {
    "RL-001": {
        "id": "RL-001",
        "layer": KernelLayer.ABSOLUTE.value,
        "category": "人机权责法定红线",
        "rule": "人类拥有100%最终决策权与全部责任承担，AI仅可提供决策辅助，绝对禁止替用户做出最终决策，禁止使用诱导性、倾向性表述引导用户做出特定决策",
        "keywords": ["替我决定", "直接选哪个", "告诉我选什么", "帮我做决定", "最优方案是", "建议您选择"],
        "severity": RedLineLevel.SEVERE.value,
        "intercept_action": "立即拒绝，重申人机权责边界"
    },
    "RL-002": {
        "id": "RL-002",
        "layer": KernelLayer.ABSOLUTE.value,
        "category": "生成校验绝对隔离红线",
        "rule": "方案生成与校验必须完全隔离，平行校验角色之间绝对禁止信息交叉、互相影响，绝对禁止生成角色自我校验、自我修改",
        "keywords": ["跳过校验", "不用验证", "省略检查", "简化流程"],
        "severity": RedLineLevel.SEVERE.value,
        "intercept_action": "终止流程，重新执行完整校验"
    },
    "RL-003": {
        "id": "RL-003",
        "layer": KernelLayer.ABSOLUTE.value,
        "category": "信息全覆盖红线",
        "rule": "必须完整披露所有支持和反对决策的正向/反向信息、数据、信号，反向信息披露占比不得低于全量内容的30%",
        "keywords": ["只说好的", "不要提风险", "忽略负面", "隐藏风险"],
        "severity": RedLineLevel.SEVERE.value,
        "intercept_action": "强制重新生成，补充反向信息"
    },
    "RL-004": {
        "id": "RL-004",
        "layer": KernelLayer.ABSOLUTE.value,
        "category": "可溯源可验证红线",
        "rule": "所有核心数据、前提、来源必须明确标注、可权威验证，绝对禁止使用无来源、无法验证的主观假设作为决策核心前提",
        "keywords": ["编造数据", "随便写个数据", "假设数据"],
        "severity": RedLineLevel.SEVERE.value,
        "intercept_action": "拦截输出，要求替换为权威数据"
    },
    "RL-005": {
        "id": "RL-005",
        "layer": KernelLayer.ABSOLUTE.value,
        "category": "合规底线红线",
        "rule": "绝对禁止输出违反国家法律法规的内容，无资质绝对禁止提供医疗、法律、金融等领域的确定性执业建议",
        "keywords": [],
        "severity": RedLineLevel.SEVERE.value,
        "intercept_action": "直接拒绝，终止流程"
    },
    "RL-006": {
        "id": "RL-006",
        "layer": KernelLayer.ABSOLUTE.value,
        "category": "分级刚性红线",
        "rule": "必须严格遵循风险分级对应的流程规则，绝对禁止为了提升效率擅自降低风险等级、裁剪核心校验环节",
        "keywords": ["降低风险等级", "用低风险流程", "简化高风险"],
        "severity": RedLineLevel.SEVERE.value,
        "intercept_action": "拒绝执行，强制使用对应流程"
    }
}


# ============================================================
# 半固定规则层 - 风险分级框架、平行校验权责划分、元监基本职能
# ============================================================

RISK_GRADING_RULES = {
    "dimensions": {
        "irreversibility": {
            "name": "决策不可逆程度",
            "weight": 0.40,
            "scale": {
                "0": "无任何不可逆影响",
                "2": "轻微不可逆，影响有限",
                "4": "部分不可逆，可补救",
                "6": "较高不可逆性，补救成本高",
                "8": "高度不可逆，重大影响",
                "10": "决策不可逆，存在致命损失风险"
            },
            "industry_weights": {
                "金融投资": 0.45,
                "法律合规": 0.30,
                "医疗健康": 0.35,
                "房地产": 0.50,
                "企业战略": 0.55,
                "默认": 0.40
            }
        },
        "compliance": {
            "name": "合规与专业度要求",
            "weight": 0.35,
            "scale": {
                "0": "无合规/专业资质要求",
                "3": "低合规要求",
                "5": "中等合规要求",
                "7": "较高合规要求",
                "10": "涉及医疗/法律/金融等强监管专业领域"
            },
            "industry_weights": {
                "金融投资": 0.40,
                "法律合规": 0.60,
                "医疗健康": 0.55,
                "房地产": 0.30,
                "企业战略": 0.25,
                "默认": 0.35
            }
        },
        "complexity": {
            "name": "信息完整度与场景复杂度",
            "weight": 0.25,
            "scale": {
                "0": "信息完整、单变量线性场景",
                "3": "信息较完整、少变量场景",
                "5": "信息部分缺失、多变量场景",
                "7": "信息缺失较多、非线性场景",
                "10": "信息严重缺失、多变量耦合混沌场景"
            },
            "industry_weights": {
                "金融投资": 0.15,
                "法律合规": 0.10,
                "医疗健康": 0.10,
                "房地产": 0.20,
                "企业战略": 0.20,
                "默认": 0.25
            }
        }
    },
    "thresholds": {
        "low": {"max_score": 3.5},
        "medium": {"min_score": 3.5, "max_score": 6.5},
        "high": {"min_score": 6.5}
    },
    "industry_baselines": {
        "金融投资": {
            "高风险触发": "单笔决策金额>=5万元",
            "高风险强制场景": ["股票投资", "基金配置", "期货", "期权", "大额理财"]
        },
        "法律合规": {
            "高风险触发": "涉及合同审核、诉讼相关需求",
            "高风险强制场景": ["合同审核", "诉讼", "合规风险排查"]
        },
        "医疗健康": {
            "高风险触发": "涉及诊疗、用药、康复需求",
            "高风险强制场景": ["疾病诊断", "用药建议", "手术方案"]
        },
        "房地产": {
            "高风险触发": "单笔决策金额>=50万元",
            "高风险强制场景": ["房产购置", "项目开发"]
        }
    }
}


# ============================================================
# 动态适配层 - 行业专项规则、数据源列表、校验清单
# ============================================================

INDUSTRY_RULES = {
    "金融投资": {
        "disclaimer": "本内容仅为决策辅助信息参考，不构成任何投资建议，投资有风险，入市需谨慎",
        "prohibited_actions": [
            "承诺投资收益、保本保收益",
            "替代用户做出买入/卖出的投资决策",
            "使用「必涨」「稳赚」「无风险」等绝对化表述",
            "为非法金融活动、非法集资、场外配资等提供决策辅助"
        ],
        "data_sources": ["证监会", "央行", "交易所", "上市公司公告"],
        "cognitive_biases": ["追涨杀跌", "锚定效应", "过度自信", "幸存者偏差", "损失厌恶"]
    },
    "法律合规": {
        "disclaimer": "本内容仅为法律信息参考，不构成律师执业意见，具体法律问题请咨询执业律师",
        "prohibited_actions": [
            "替代执业律师出具法律意见书、律师函",
            "承诺诉讼结果、胜诉概率",
            "为违法犯罪行为提供规避法律的方案"
        ],
        "data_sources": ["中国人大网", "最高法官网", "权威法律法规数据库"],
        "cognitive_biases": ["确认偏误", "框架效应", "可用性启发"]
    },
    "医疗健康": {
        "disclaimer": "本内容仅为健康科普信息参考，不构成诊疗建议，具体诊疗请前往正规医疗机构",
        "prohibited_actions": [
            "替代执业医师做出疾病诊断、出具诊疗方案",
            "推荐未经国家药监局批准的药品、医疗器械",
            "宣传偏方、虚假医疗信息"
        ],
        "data_sources": ["国家卫健委", "国家药监局", "中华医学会", "权威医学期刊"],
        "cognitive_biases": ["安慰剂效应", "可得性偏差", "代表性启发"]
    },
    "房地产": {
        "disclaimer": "本内容仅为决策辅助信息参考，不构成任何投资或购房建议",
        "prohibited_actions": [
            "承诺房价涨跌、投资收益",
            "为违规开发、违建、规避监管的行为提供方案",
            "使用虚假的市场数据、规划信息误导用户"
        ],
        "data_sources": ["政府官网", "住建局", "自然资源局", "统计局"],
        "cognitive_biases": ["锚定效应", "禀赋效应", "从众效应"]
    }
}


# ============================================================
# 核心认知偏差清单（12类）
# ============================================================

COGNITIVE_BIASES = [
    {"id": "CB-001", "name": "确认偏误", "description": "倾向于寻找、解释和记忆能确认自己已有信念的信息", "severity": "高"},
    {"id": "CB-002", "name": "锚定效应", "description": "过度依赖最先接收到的信息（锚点）做后续判断", "severity": "高"},
    {"id": "CB-003", "name": "损失厌恶", "description": "损失的痛苦感约为同等收益快乐感的2倍，导致风险规避过度", "severity": "高"},
    {"id": "CB-004", "name": "过度自信", "description": "高估自身知识、能力和预测准确性的倾向", "severity": "中"},
    {"id": "CB-005", "name": "可得性偏差", "description": "根据信息在记忆中的易得程度来判断事件概率", "severity": "中"},
    {"id": "CB-006", "name": "代表性启发", "description": "根据事物与某个原型的相似程度来判断其属于某类别的概率", "severity": "中"},
    {"id": "CB-007", "name": "框架效应", "description": "同一信息的不同表述方式会导致不同的决策偏好", "severity": "高"},
    {"id": "CB-008", "name": "从众效应", "description": "倾向于跟随多数人的观点或行为，即使缺乏合理依据", "severity": "中"},
    {"id": "CB-009", "name": "沉没成本谬误", "description": "因为已经投入的资源而继续坚持一个不明智的决策", "severity": "高"},
    {"id": "CB-010", "name": "幸存者偏差", "description": "只关注成功案例而忽略失败案例，导致对成功概率的过高估计", "severity": "高"},
    {"id": "CB-011", "name": "禀赋效应", "description": "对已拥有物品的估值高于未拥有时", "severity": "中"},
    {"id": "CB-012", "name": "因果倒置", "description": "错误地将结果当作原因，或混淆因果关系", "severity": "高"}
]


# ============================================================
# 核心内核类
# ============================================================

class GradientKernel:
    """梯度式内核 - 全体系唯一复用根基"""
    
    def __init__(self):
        self._absolute_rules = ABSOLUTE_RED_LINES
        self._risk_grading_rules = RISK_GRADING_RULES
        self._risk_rules = RISK_GRADING_RULES
        self._industry_rules = INDUSTRY_RULES
        self._cognitive_biases = COGNITIVE_BIASES
        self._violation_count = {}  # 用户违规计数
    
    def get_red_lines(self) -> Dict:
        """获取所有红线规则"""
        return self._absolute_rules
    
    def get_risk_grading_rules(self, industry: str = "默认") -> Dict:
        """获取风险分级规则（按行业适配权重）"""
        rules = self._risk_grading_rules.copy()
        dims = rules["dimensions"]
        for dim_key, dim_val in dims.items():
            if dim_key in dim_val and industry in dim_val.get("industry_weights", {}):
                dims[dim_key]["current_weight"] = dim_val["industry_weights"][industry]
            else:
                dims[dim_key]["current_weight"] = dim_val["weight"]
        return rules
    
    def get_industry_rules(self, industry: str) -> Optional[Dict]:
        """获取行业专项规则"""
        return self._industry_rules.get(industry)
    
    def get_cognitive_biases(self) -> List[Dict]:
        """获取核心认知偏差清单"""
        return self._cognitive_biases
    
    def check_red_line_violation(self, user_input: str, user_id: str = "anonymous") -> Tuple[bool, Optional[Dict]]:
        """
        检查用户输入是否触发红线违规
        返回: (是否违规, 违规详情)
        """
        violations = []
        for rule_id, rule in self._absolute_rules.items():
            for keyword in rule.get("keywords", []):
                if keyword in user_input:
                    violations.append(rule)
                    break
        
        if not violations:
            return False, None
        
        # 判断违规严重程度
        severity_counts = {}
        for v in violations:
            s = v["severity"]
            severity_counts[s] = severity_counts.get(s, 0) + 1
        
        # 更新用户违规计数
        if user_id not in self._violation_count:
            self._violation_count[user_id] = {"light": 0, "medium": 0, "severe": 0}
        
        if severity_counts.get(RedLineLevel.SEVERE.value, 0) > 0:
            self._violation_count[user_id]["severe"] += 1
            return True, {
                "level": RedLineLevel.SEVERE.value,
                "message": "严重违规：触发核心红线规则",
                "violations": violations,
                "action": "终止当前对话，重新唤醒系统核心规则",
                "user_violations": self._violation_count[user_id]
            }
        elif severity_counts.get(RedLineLevel.MEDIUM.value, 0) > 0 or self._violation_count[user_id]["light"] >= 1:
            self._violation_count[user_id]["medium"] += 1
            return True, {
                "level": RedLineLevel.MEDIUM.value,
                "message": "中度违规：核心红线行为或累计违规",
                "violations": violations,
                "action": "终止当前流程，重新唤醒核心规则",
                "user_violations": self._violation_count[user_id]
            }
        else:
            self._violation_count[user_id]["light"] += 1
            return True, {
                "level": RedLineLevel.LIGHT.value,
                "message": "轻度违规：非核心红线行为",
                "violations": violations,
                "action": "发出风险提示，拒绝执行违规指令",
                "user_violations": self._violation_count[user_id]
            }
    
    def reset_user_violations(self, user_id: str):
        """重置用户违规计数"""
        self._violation_count[user_id] = {"light": 0, "medium": 0, "severe": 0}
    
    def check_rule_conflict(self, industries: List[str]) -> Optional[Dict]:
        """
        规则冲突仲裁引擎
        检测跨行业、跨场景的规则冲突
        """
        if len(industries) <= 1:
            return None
        
        rules_list = []
        for ind in industries:
            r = self._industry_rules.get(ind)
            if r:
                rules_list.append({"industry": ind, "rules": r})
        
        conflicts = []
        for i, r1 in enumerate(rules_list):
            for r2 in rules_list[i+1:]:
                # 检查免责声明冲突
                if r1["rules"]["disclaimer"] != r2["rules"]["disclaimer"]:
                    conflicts.append({
                        "type": "免责声明差异",
                        "between": [r1["industry"], r2["industry"]],
                        "detail": f"{r1['industry']}和{r2['industry']}的合规免责声明不同，需用户确认适用哪套规则"
                    })
                # 检查禁止行为冲突
                set1 = set(r1["rules"]["prohibited_actions"])
                set2 = set(r2["rules"]["prohibited_actions"])
                if set1 != set2:
                    conflicts.append({
                        "type": "禁止行为差异",
                        "between": [r1["industry"], r2["industry"]],
                        "detail": f"{r1['industry']}和{r2['industry']}的禁止行为清单不同"
                    })
        
        if conflicts:
            return {
                "has_conflict": True,
                "conflicts": conflicts,
                "resolution": "请用户最终裁定适用的行业规则",
                "industries_involved": industries
            }
        return None
    
    def validate_kernel_integrity(self) -> Dict:
        """内核完整性自检"""
        checks = {
            "red_lines_count": len(self._absolute_rules),
            "red_lines_complete": len(self._absolute_rules) == 6,
            "risk_dimensions_count": len(self._risk_grading_rules["dimensions"]),
            "risk_dimensions_complete": len(self._risk_grading_rules["dimensions"]) == 3,
            "industry_rules_count": len(self._industry_rules),
            "cognitive_biases_count": len(self._cognitive_biases),
            "cognitive_biases_complete": len(self._cognitive_biases) == 12,
            "all_checks_passed": False
        }
        checks["all_checks_passed"] = all([
            checks["red_lines_complete"],
            checks["risk_dimensions_complete"],
            checks["cognitive_biases_complete"]
        ])
        return checks
