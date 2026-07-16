from collections import defaultdict
from threading import Lock


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.total = 0
        self.by_type: dict[str, dict] = defaultdict(
            lambda: {"total": 0, "success": 0, "failed": 0, "timeout": 0, "durations": []}
        )

    def record(self, query_type: str, status: str, duration_ms: float) -> None:
        with self._lock:
            self.total += 1
            bucket = self.by_type[query_type]
            bucket["total"] += 1
            if status == "success":
                bucket["success"] += 1
            elif status == "timeout":
                bucket["timeout"] += 1
            else:
                bucket["failed"] += 1
            bucket["durations"].append(duration_ms)

    def snapshot(self) -> dict:
        with self._lock:
            out = {}
            for key, bucket in self.by_type.items():
                durations = bucket["durations"]
                avg = sum(durations) / len(durations) if durations else 0.0
                out[key] = {
                    "total": bucket["total"],
                    "success": bucket["success"],
                    "failed": bucket["failed"],
                    "timeout": bucket["timeout"],
                    "avg_ms": round(avg, 1),
                }
            return {"total": self.total, "by_type": out}


metrics = Metrics()
