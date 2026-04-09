from ..core.models import SignalResult

_weights = {
    "payload": 0.40,
    "behavior": 0.35,
    "identity": 0.25,
}


def compute_score(sig_res: dict[str, SignalResult], snap=None) -> tuple[float, dict[str, float]]:
    breakdown: dict[str, float] = {}
    total = 0.0
    active = 0

    weights = {
        "payload": snap.payload_weight if snap else _weights["payload"],
        "behavior": snap.behavior_weight if snap else _weights["behavior"],
        "identity": snap.identity_weight if snap else _weights["identity"],
    }

    for name, res in sig_res.items():
        weight = weights.get(name, 0.0)
        part = res.score * weight
        breakdown[name] = part
        total += part
        if res.score > 0.0:
            active += 1

    if active > 1:
        total += 0.01

    return min(total, 1.0), breakdown
