from datetime import date, timedelta
from typing import Optional


def parse_date(raw: str, base: Optional[date] = None) -> Optional[str]:
    """解析相对/绝对日期字符串（保留辅助函数）。"""
    import re

    base = base or date.today()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{1,2})月(\d{1,2})日", raw)
    if m:
        month = int(m.group(1))
        day = int(m.group(2))
        try:
            d = date(base.year, month, day)
            if d < base:
                d = date(base.year + 1, month, day)
            return d.isoformat()
        except ValueError:
            return None
    if "大后天" in raw:
        return (base + timedelta(days=3)).isoformat()
    if "后天" in raw:
        return (base + timedelta(days=2)).isoformat()
    if "明天" in raw or "明日" in raw:
        return (base + timedelta(days=1)).isoformat()
    if "今天" in raw or "今日" in raw:
        return base.isoformat()
    return None
