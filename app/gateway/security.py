"""提示词注入检测。

检测用户输入中的常见注入模式，在网关层拦截。
"""

import re

# 注入模式列表：(正则, 风险等级)
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 指令覆盖类
    (re.compile(r"忽略(所有|之前|前面|上述)(的|所有)?(指令|指示|规则|要求)", re.I), "high"),
    (re.compile(r"ignore\s+(all\s+)?(previous|above)\s+(instructions?|prompts?)", re.I), "high"),
    # 角色篡改类
    (re.compile(r"(你现在|从现在开始|you\s+are\s+now).{0,10}(是|扮演|作为|就是|变成).{0,20}(助手|角色|AI|DAN|黑客)", re.I), "high"),
    (re.compile(r"you\s+are\s+(now\s+)?DAN", re.I), "high"),
    # 分隔符注入
    (re.compile(r"_{3,}|-{3,}|#{1,6}\s*(system|user|assistant|指令|规则)", re.I), "medium"),
    # 嵌套指令
    (re.compile(r"<\|.{2,}\|>", re.I), "medium"),
    (re.compile(r"\[INST\].*\[/INST\]", re.I), "high"),
    # 输出泄露
    (re.compile(r"(重复|输出|打印|告诉我|说出|显示)(你|你的)?.*?(系统|原始)?(提示词|prompt|指令|规则|设定)", re.I), "high"),
    (re.compile(r"(repeat|output|print|tell\s+me|show)\s+(your\s+)?(system\s+)?(prompt|instructions?)", re.I), "high"),
]


def detect_injection(raw: str) -> list[dict]:
    """检测用户输入中的注入风险。

    Returns:
        命中模式列表: [{"pattern": str, "risk": "high"|"medium"}, ...]
        空列表表示未检测到风险。
    """
    hits: list[dict] = []
    for pattern, risk in _INJECTION_PATTERNS:
        if pattern.search(raw):
            hits.append({"pattern": pattern.pattern, "risk": risk})
    return hits


def is_suspicious(raw: str) -> bool:
    """快速判断输入是否有注入嫌疑。"""
    return len(detect_injection(raw)) > 0
