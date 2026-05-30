from __future__ import annotations

from dataclasses import dataclass

from .models import RolePreset


@dataclass(frozen=True)
class Criterion:
    title: str
    keywords: tuple[str, ...]
    action: str
    question_seed: str


ROLE_RUBRICS: dict[RolePreset, tuple[Criterion, ...]] = {
    RolePreset.ENGINEERING: (
        Criterion("核心技术栈匹配", ("react", "node", "typescript", "python", "java", "go", "postgresql"), "把最匹配 JD 的技术栈证据前置，并补充量化结果。", "请展开一个最能证明技术栈深度的项目。"),
        Criterion("系统设计与可扩展性", ("system design", "架构", "可扩展", "高并发", "分布式", "服务"), "准备一个系统设计案例，说明约束、取舍和结果。", "如果流量增加 10 倍，你会怎么改造现有方案？"),
        Criterion("性能与可靠性", ("性能", "优化", "latency", "可用性", "稳定性", "监控"), "整理性能或可靠性案例，补充指标前后对比。", "你如何定位并修复一次线上性能问题？"),
        Criterion("协作与技术影响力", ("跨团队", "推动", "评审", "带领", "mentor", "文档"), "准备一次推动跨团队或技术决策的 STAR 故事。", "讲一次你推动团队采用某个技术方案的经历。"),
    ),
    RolePreset.PRODUCT: (
        Criterion("用户问题与需求定义", ("用户访谈", "需求", "痛点", "场景", "prd"), "补充用户问题、目标用户和需求取舍过程。", "你如何判断一个需求是否值得做？"),
        Criterion("数据分析与指标", ("数据", "指标", "漏斗", "sql", "ab", "a/b", "实验"), "准备一个用数据定义问题并验证上线效果的案例。", "你如何设计并评估一次 A/B 测试？"),
        Criterion("跨职能推进", ("研发", "设计", "运营", "销售", "协作", "推进"), "整理一次跨团队推进中的冲突、决策和结果。", "需求冲突时你如何排序和沟通？"),
        Criterion("商业化或增长", ("增长", "转化", "定价", "商业化", "留存", "生命周期"), "补齐增长/商业化相关案例，至少准备一个指标拆解。", "你会如何提升这个产品的转化率？"),
    ),
    RolePreset.OPERATIONS: (
        Criterion("用户分层与生命周期", ("分层", "生命周期", "留存", "召回", "活跃"), "准备用户分层策略和不同人群运营动作。", "你会如何为不同活跃度用户设计运营策略？"),
        Criterion("活动与社群运营", ("活动", "社群", "内容", "报名", "转化", "复盘"), "整理活动目标、执行节奏、转化数据和复盘结论。", "讲一次活动效果不达预期后你怎么复盘。"),
        Criterion("数据复盘", ("数据", "复盘", "指标", "看板", "转化", "roi"), "准备一套运营指标拆解和复盘模板。", "你如何判断一个运营动作是否有效？"),
        Criterion("工具与自动化", ("crm", "自动化", "投放", "预算", "渠道"), "补充 CRM、投放或自动化经验；没有证据时准备学习方案。", "如果给你一套 CRM，你会先搭哪些自动化流程？"),
    ),
    RolePreset.GENERIC: (
        Criterion("岗位硬性要求", ("要求", "必须", "经验", "能力"), "逐条补齐 JD 硬性要求对应的简历证据。", "你最匹配这个岗位的证据是什么？"),
        Criterion("结果量化", ("提升", "降低", "增长", "减少", "转化", "效率"), "把经历改写成动作、指标和结果。", "你做过最有业务结果的一件事是什么？"),
        Criterion("协作表达", ("协作", "沟通", "推进", "跨团队"), "准备跨团队沟通的 STAR 案例。", "讲一次你处理分歧的经历。"),
    ),
}


ROLE_KEYWORDS: dict[RolePreset, tuple[str, ...]] = {
    RolePreset.ENGINEERING: ("engineer", "developer", "frontend", "backend", "fullstack", "react", "node", "java", "python", "golang", "工程师", "研发", "前端", "后端", "全栈"),
    RolePreset.PRODUCT: ("product manager", "growth", "prd", "产品", "产品经理", "增长", "需求", "用户故事"),
    RolePreset.OPERATIONS: ("operations", "operator", "运营", "用户运营", "内容运营", "社群", "活动", "crm"),
}


def infer_role(jd_text: str) -> tuple[RolePreset, float]:
    lower = jd_text.lower()
    scores = {
        role: sum(1 for keyword in keywords if keyword.lower() in lower)
        for role, keywords in ROLE_KEYWORDS.items()
    }
    best_role, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score == 0:
        return RolePreset.GENERIC, 0.25
    total = sum(scores.values())
    confidence = min(0.95, 0.45 + best_score / max(total, 1) * 0.5)
    return best_role, confidence


def rubric_for(role: RolePreset) -> tuple[Criterion, ...]:
    return ROLE_RUBRICS.get(role, ROLE_RUBRICS[RolePreset.GENERIC])

