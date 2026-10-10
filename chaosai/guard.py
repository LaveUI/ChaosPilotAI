"""Step 3 safety: automatic abort on error rate, latency, or blast radius, plus a manual stop file."""
import os


class Guard:
    def __init__(self, cfg, baseline, stop_file):
        s = cfg["safety"]
        self.max_err = s["max_error_rate"]
        self.lat_limit = max(s["min_p95_ms"], baseline["p95_ms"] * s["p95_factor"])
        self.max_unhealthy = s["max_extra_unhealthy_pods"]
        self.stop_file = stop_file

    def limits(self):
        return {"max_error_rate": self.max_err, "p95_limit_ms": round(self.lat_limit),
                "max_extra_unhealthy_pods": self.max_unhealthy}

    def check(self, err_rate, p95_ms, extra_unhealthy):
        """Return a reason string if the experiment must stop, else None."""
        if os.path.exists(self.stop_file):
            return "manual stop requested"
        if err_rate > self.max_err:
            return f"error rate {err_rate:.0%} exceeded limit {self.max_err:.0%}"
        if p95_ms > self.lat_limit:
            return f"p95 latency {p95_ms:.0f} ms exceeded limit {self.lat_limit:.0f} ms"
        if extra_unhealthy > self.max_unhealthy:
            return f"blast radius: {extra_unhealthy} extra unhealthy pods (limit {self.max_unhealthy})"
        return None
