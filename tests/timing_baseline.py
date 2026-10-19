import json
import time
from pathlib import Path

SLOWER = 1.25
FLOOR = 0.001
DEFAULT_PATH = Path(__file__).resolve().parent.parent / ".timing-baseline.json"


def keep_busy(seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


def best_of(fn, runs: int = 5, warm_s: float = 0.05) -> float:
    end = time.perf_counter() + warm_s
    while time.perf_counter() < end:
        fn()
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return min(times)


class TimingBaseline:
    def __init__(self, path: Path = DEFAULT_PATH, reset: bool = False):
        self.path = Path(path)
        self.reset = reset
        self.records = json.loads(self.path.read_text()) if self.path.exists() else {}

    def judge(self, name: str, seconds: float, limit: float) -> str | None:
        if seconds >= limit:
            return f"{name}: {seconds * 1000:.1f} ms, limit {limit * 1000:.1f} ms"
        recorded = self.records.get(name)
        if recorded is None or self.reset:
            self.records[name] = seconds
            self.path.write_text(json.dumps(self.records, indent=1, sort_keys=True) + "\n")
            return None
        if seconds >= recorded * SLOWER and seconds - recorded >= FLOOR:
            return (f"{name}: {seconds * 1000:.1f} ms, recorded {recorded * 1000:.1f} ms, "
                    f"limit {limit * 1000:.1f} ms; if this slowdown is accepted, run with "
                    f"--reset-timing-baseline")
        return None

    def assert_within(self, timings: dict[str, tuple[float, float]]) -> None:
        failures = [self.judge(name, seconds, limit) for name, (seconds, limit) in timings.items()]
        failures = [f for f in failures if f]
        assert not failures, "\n".join(failures)
