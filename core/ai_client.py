# AI 大模型调用模块
# 支持 OpenAI 兼容接口，实现多模型独立调用

import json
import os
import time
from typing import Dict, List, Optional, Generator
from dataclasses import dataclass, field

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

from config import Config


@dataclass
class LLMMessage:
    """LLM 消息"""
    role: str  # system / user / assistant
    content: str


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    usage: Dict = field(default_factory=dict)
    latency_ms: float = 0.0
    success: bool = True
    error: str = ""


class LLMClient:
    """
    AI 大模型调用客户端
    - 支持 OpenAI 兼容 API（OpenAI / 智谱 / 通义 / DeepSeek 等）
    - 支持多模型独立调用（时序隔离的关键）
    - 流式输出支持
    - 自动重试与降级
    """

    def __init__(self, api_key: str = None, api_base: str = None, model: str = None):
        self.api_key = api_key or Config.AI_API_KEY
        self.api_base = api_base or Config.AI_API_BASE
        self.default_model = model or Config.AI_MODEL_PRIMARY
        self._clients = {}  # 缓存不同配置的 client

    def _get_client(self, api_key: str = None, api_base: str = None) -> Optional['OpenAI']:
        """获取或创建 OpenAI client（带缓存）"""
        if not HAS_OPENAI:
            return None
        key = (api_key or self.api_key, api_base or self.api_base)
        if key not in self._clients:
            try:
                self._clients[key] = OpenAI(
                    api_key=key[0],
                    base_url=key[1],
                    timeout=60.0
                )
            except Exception:
                return None
        return self._clients[key]

    def is_available(self) -> bool:
        """检查 AI 是否可用"""
        if not self.api_key:
            return False
        client = self._get_client()
        return client is not None

    def chat(
        self,
        messages: List[LLMMessage],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict = None,
        api_key: str = None,
        api_base: str = None
    ) -> LLMResponse:
        """
        非流式调用 LLM
        
        Args:
            messages: 消息列表
            model: 模型名称（不填用默认）
            temperature: 温度（0-2）
            max_tokens: 最大 token 数
            response_format: 响应格式（如 {"type": "json_object"}）
            api_key/api_base: 可覆盖默认配置（用于多模型隔离）
        """
        start = time.time()
        
        client = self._get_client(api_key, api_base)
        if not client:
            return LLMResponse(
                content="",
                model=model or self.default_model,
                success=False,
                error="AI服务不可用：请检查 API Key 和 API Base 配置"
            )

        # 构建消息
        msg_list = [{"role": m.role, "content": m.content} for m in messages]
        
        kwargs = {
            "model": model or self.default_model,
            "messages": msg_list,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        try:
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            usage = {}
            if resp.usage:
                usage = {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                    "total_tokens": resp.usage.total_tokens
                }
            
            return LLMResponse(
                content=content,
                model=resp.model,
                usage=usage,
                latency_ms=round((time.time() - start) * 1000, 1),
                success=True
            )
        except Exception as e:
            return LLMResponse(
                content="",
                model=model or self.default_model,
                success=False,
                error=f"AI调用失败: {str(e)}"
            )

    def chat_stream(
        self,
        messages: List[LLMMessage],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Generator[str, None, None]:
        """流式调用 LLM，逐块 yield 文本"""
        client = self._get_client()
        if not client:
            yield "[AI服务不可用]"
            return

        msg_list = [{"role": m.role, "content": m.content} for m in messages]
        
        try:
            stream = client.chat.completions.create(
                model=model or self.default_model,
                messages=msg_list,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"[AI调用失败: {str(e)}]"

    def chat_json(
        self,
        messages: List[LLMMessage],
        model: str = None,
        temperature: float = 0.3,
        **kwargs
    ) -> LLMResponse:
        """调用 LLM 并尝试解析 JSON 响应"""
        # 确保系统提示要求 JSON
        if messages and messages[0].role == "system":
            original_system = messages[0].content
            if "JSON" not in original_system and "json" not in original_system:
                messages[0] = LLMMessage(
                    role="system",
                    content=original_system + "\n\n请以 JSON 格式返回结果，不要输出其他内容。"
                )

        resp = self.chat(messages, model=model, temperature=temperature, **kwargs)
        if not resp.success:
            return resp

        # 尝试解析 JSON
        content = resp.content.strip()
        # 处理 markdown 代码块包裹的情况
        if content.startswith("```"):
            lines = content.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            content = "\n".join(lines)

        try:
            json.loads(content)
        except json.JSONDecodeError:
            # 尝试修复常见问题
            try:
                json.loads(content.encode('utf-8').decode('unicode_escape'))
            except:
                pass  # 保持原样，让调用方处理

        return resp


# ---- 灵境系统专用 Prompt 工程 ----

class LingjingPrompts:
    """灵境系统的 Prompt 模板库"""

    # ==================== 需求深度解析 ====================
    
    REQUIREMENT_ANALYSIS_SYSTEM = """你是一个专业的决策需求分析专家。你的任务是深入理解用户的自然语言需求，将其拆解为结构化的决策要素。

请严格按以下 JSON 格式返回：
{
    "decision_goal": "提炼的核心决策目标（一句话）",
    "boundary_scope": "决策的边界和范围",
    "precision_requirement": "精度要求（高/中/低）",
    "risk_exposure": "潜在风险敞口描述",
    "constraints": "用户提及的约束条件",
    "budget": "预算/金额（如有）",
    "time_cycle": "时间周期（如有）",
    "industry": "所属行业分类",
    "emotion_tone": "用户情绪基调（焦虑/冷静/急迫/犹豫/坚定）",
    "information_completeness": "信息完整度评估（充足/一般/不足/严重不足）",
    "missing_info": ["缺失的关键信息1", "缺失的关键信息2"],
    "core_dilemma": "用户面临的核心矛盾或两难（如有）",
    "summary": "对需求的整体理解（2-3句话）"
}

行业分类选项：金融投资、法律合规、医疗健康、房地产、企业战略、教育、职业发展、消费决策、人际决策、其他"""

    @classmethod
    def build_requirement_analysis(cls, user_input: str) -> List[LLMMessage]:
        return [
            LLMMessage(role="system", content=cls.REQUIREMENT_ANALYSIS_SYSTEM),
            LLMMessage(role="user", content=f"请分析以下决策需求：\n\n{user_input}")
        ]

    # ==================== 方案生成 ====================

    SCHEME_GENERATION_SYSTEM = """你是「灵境理性决策辅助系统」的核心方案生成引擎。你的职责是为用户生成高质量、全面、无偏的决策辅助方案。

核心原则（不可违反）：
1. 绝不替用户做决定——你提供信息和分析，用户自行决策
2. 绝不使用"最优方案"、"建议您直接"、"保证"等倾向性表述
3. 必须同时呈现正向信息和反向风险信息
4. 每个方案必须包含：核心逻辑、收益预期、风险敞口、适用场景、触发条件/止损线、置信度
5. 高风险场景必须列出至少5个核心致命风险和5个次要风险
6. 所有数据主张必须标注来源或注明"需进一步核验"

你的输出将经过三个独立校验官审查，请确保内容经得起最严格的检验。"""

    @classmethod
    def build_scheme_generation(
        cls,
        user_input: str,
        requirement_analysis: Dict,
        risk_grade: str,
        scheme_type: str,  # optimistic/neutral/pessimistic/conservative/balanced/aggressive
        scheme_label: str
    ) -> List[LLMMessage]:
        type_instructions = {
            "optimistic": "你正在生成【乐观方案】。请基于最有利的假设条件，分析可能的收益空间，但不可粉饰风险。",
            "neutral": "你正在生成【中性方案】。请基于最可能的情景，提供平衡、客观的分析。",
            "pessimistic": "你正在生成【悲观方案】。请基于最不利的假设条件，重点分析风险敞口和最大损失，但不可过度渲染。",
            "conservative": "你正在生成【保守方案】。请以风险最小化为优先目标，分析稳健策略。",
            "balanced": "你正在生成【稳健方案】。请在收益和风险之间寻求平衡。",
            "aggressive": "你正在生成【进取方案】。请以收益最大化为优先目标，但必须充分披露风险。"
        }

        risk_instructions = {
            "low": "当前为【低风险】决策，提供简洁实用的分析即可。",
            "medium": "当前为【中风险】决策，需要提供较为全面的分析，包含风险提示。",
            "high": "当前为【高风险】决策，必须提供全景式深度分析，包含极端情景评估、尾部风险分析。每个风险必须标注发生概率区间和最大损失估算。"
        }

        user_msg = f"""用户原始需求：{user_input}

需求分析结果：
{json.dumps(requirement_analysis, ensure_ascii=False, indent=2)}

{type_instructions.get(scheme_type, '')}
{risk_instructions.get(risk_grade, '')}

请生成【{scheme_label}】，严格按以下结构输出：

## {scheme_label}

### 一、核心逻辑
（详细阐述方案的核心推理逻辑）

### 二、前提假设
（列出该方案成立的关键前提条件）

### 三、收益预期
（量化或定性描述预期收益）

### 四、风险敞口分析
**致命风险**（至少5个，每个标注概率区间和最大损失）：
1. ...
**次要风险**（至少5个）：
1. ...
**尾部风险/极端情景**：
（最坏情况分析）

### 五、适用场景与不适用场景

### 六、关键触发条件与止损线
（什么条件下应该退出/调整）

### 七、数据来源与置信度
（标注所有数据主张的来源或注明"需进一步核验"）

### 八、认知偏差自查
（自查本方案可能存在的分析盲点）

### 九、反向信息与弱信号
（可能被忽视的早期预警信号、与主流观点相反的论据）"""

        return [
            LLMMessage(role="system", content=cls.SCHEME_GENERATION_SYSTEM),
            LLMMessage(role="user", content=user_msg)
        ]

    # ==================== 三维平行校验 ====================

    CHECKER_1_SYSTEM = """你是「灵境系统」的【前提依据校验官】（校验官 #1）。

你的唯一职责：校验方案的核心前提、数据来源、信息真实性/完整性/时效性。
你绝对禁止触碰逻辑推导内容和框架匹配内容。

校验标准：
1. 核心前提是否有可靠来源支撑
2. 数据来源是否权威、是否可验证
3. 是否存在"无来源主观假设"
4. 是否刻意隐瞒了重要的反向信息
5. 关键数据是否标注了时效性
6. 置信度标注是否合理

红色否决项（任何一项出现即标记红色）：
- 无来源主观假设被当作事实使用
- 刻意隐瞒重大反向信息
- 数据造假或严重歪曲

请严格按以下 JSON 格式返回：
{
    "result": "pass 或 fail",
    "issues": [
        {"level": "fatal/warning/info", "item": "问题项", "description": "问题描述", "suggestion": "整改建议"}
    ],
    "red_flags": ["红色否决项列表"],
    "data_verification": [
        {"claim": "方案中的数据主张", "verdict": "已验证/待核验/无法验证", "source": "建议的验证来源"}
    ],
    "overall_assessment": "总体评估（2-3句话）"
}

注意：只关注前提和数据的真实性，不要评价逻辑是否正确。"""

    CHECKER_2_SYSTEM = """你是「灵境系统」的【逻辑推导校验官】（校验官 #2）。

你的唯一职责：校验方案的逻辑链条、推导严谨性、是否存在认知偏差。
你绝对禁止触碰前提真实性内容和框架匹配内容。

校验标准：
1. 因果关系是否成立（是否存在因果倒置）
2. 推导过程是否严谨（是否存在循环论证）
3. 是否存在线性外推陷阱
4. 是否存在12类核心认知偏差中的任何一种
5. 概率评估是否合理（是否存在过度自信）
6. 结论是否被前提充分支撑

12类核心认知偏差：确认偏误、锚定效应、可得性偏差、代表性启发、过度自信、损失厌恶、沉没成本谬误、从众效应、禀赋效应、框架效应、幸存者偏差、后见之明偏误

红色否决项：
- 因果倒置
- 循环论证
- 线性外推导致严重误判
- 存在核心认知偏差且影响结论

请严格按以下 JSON 格式返回：
{
    "result": "pass 或 fail",
    "issues": [
        {"level": "fatal/warning/info", "item": "问题项", "description": "问题描述", "suggestion": "整改建议"}
    ],
    "red_flags": ["红色否决项列表"],
    "detected_biases": ["检测到的认知偏差列表"],
    "logic_chain_assessment": "逻辑链评估",
    "overall_assessment": "总体评估（2-3句话）"
}

注意：只关注逻辑和认知偏差，不要评价数据来源是否可靠。"""

    CHECKER_3_SYSTEM = """你是「灵境系统」的【框架与风险校验官】（校验官 #3）。

你的唯一职责：校验方案框架与场景的匹配度、风险覆盖完整性、弱信号捕捉。
你绝对禁止触碰前提真实性内容和逻辑推导内容。

校验标准：
1. 框架是否匹配实际决策场景
2. 风险覆盖是否完整（是否有遗漏的重大风险）
3. 尾部风险是否被充分分析
4. 6类弱信号是否被捕捉（政策转向、技术颠覆、竞争格局突变、需求萎缩、供应链中断、黑天鹅事件）
5. 适用场景和触发条件是否明确
6. 止损/退出机制是否完善

红色否决项：
- 框架严重错配（用错分析框架）
- 尾部风险完全遗漏
- 关键弱信号缺失导致严重误判

请严格按以下 JSON 格式返回：
{
    "result": "pass 或 fail",
    "issues": [
        {"level": "fatal/warning/info", "item": "问题项", "description": "问题描述", "suggestion": "整改建议"}
    ],
    "red_flags": ["红色否决项列表"],
    "weak_signals": ["可能被忽视的弱信号"],
    "risk_gaps": ["风险覆盖缺口"],
    "overall_assessment": "总体评估（2-3句话）"
}

注意：只关注框架匹配和风险覆盖，不要评价数据来源和逻辑推导。"""

    @classmethod
    def build_checker_prompt(cls, checker_id: int, user_input: str, scheme_content: str, risk_grade: str) -> List[LLMMessage]:
        """构建校验官的 prompt（严格时序隔离：每个校验官只看到方案内容，看不到其他校验官的结果）"""
        systems = {
            1: cls.CHECKER_1_SYSTEM,
            2: cls.CHECKER_2_SYSTEM,
            3: cls.CHECKER_3_SYSTEM
        }
        
        user_msg = f"""用户决策需求：{user_input}

风险等级：{risk_grade}

以下是待校验的方案内容：

---
{scheme_content}
---

请执行你的校验职责，严格按要求的 JSON 格式返回校验结果。"""

        return [
            LLMMessage(role="system", content=systems[checker_id]),
            LLMMessage(role="user", content=user_msg)
        ]

    # ==================== 第四中立模型复核 ====================

    NEUTRAL_REVIEW_SYSTEM = """你是「灵境系统」的【第四中立模型】。你的职责是对存在争议的校验结果进行独立复核。

一个校验官提出了红色否决项，另一个或两个校验官未提出。你需要：
1. 独立审查该红色否决项是否合理
2. 做出最终裁定

裁定选项：
- "uphold"：维持否决（确认问题存在）
- "downgrade"：降级为警告（问题存在但不致命）
- "override"：推翻否决（问题不存在或被误判）

请严格按以下 JSON 格式返回：
{
    "triggered_by": "触发复核的校验官",
    "red_flag_content": "红色否决项内容",
    "independent_assessment": "你的独立评估",
    "final_verdict": "uphold / downgrade / override",
    "verdict_reason": "裁定理由",
    "requirements": ["后续要求列表"]
}"""

    @classmethod
    def build_neutral_review(cls, checker_report: Dict, other_reports: Dict, scheme_content: str) -> List[LLMMessage]:
        return [
            LLMMessage(role="system", content=cls.NEUTRAL_REVIEW_SYSTEM),
            LLMMessage(role="user", content=f"""提出红色否决项的校验官报告：
{json.dumps(checker_report, ensure_ascii=False, indent=2)}

其他校验官的报告：
{json.dumps(other_reports, ensure_ascii=False, indent=2)}

待复核的方案内容摘要：
{scheme_content[:2000]}

请执行独立复核，给出最终裁定。""")
        ]

    # ==================== 全景输出整合 ====================

    OUTPUT_INTEGRATION_SYSTEM = """你是「灵境系统」的输出整合引擎。你的任务是将方案生成和校验结果整合为一份完整的、用户友好的决策辅助报告。

要求：
1. 整合三个方案的分析（如适用）
2. 融入校验官发现的问题和风险标注
3. 保持中立、客观，绝不替用户做决定
4. 使用清晰的结构和标题
5. 高风险场景必须在最开头放置强风险提示
6. 确保风险信息占比不低于30%

输出格式：Markdown"""

    @classmethod
    def build_output_integration(
        cls,
        user_input: str,
        risk_grade: str,
        schemes: List[Dict],
        check_results: Dict,
        requirement_analysis: Dict
    ) -> List[LLMMessage]:
        return [
            LLMMessage(role="system", content=cls.OUTPUT_INTEGRATION_SYSTEM),
            LLMMessage(role="user", content=f"""用户需求：{user_input}
风险等级：{risk_grade}
需求分析：{json.dumps(requirement_analysis, ensure_ascii=False)}

方案内容：
{json.dumps(schemes, ensure_ascii=False, indent=2)}

校验结果：
{json.dumps(check_results, ensure_ascii=False, indent=2)}

请整合为一份完整的决策辅助报告。""")
        ]
