def compute_verdict(score: float, snap=None, identity_risk: float = 0.0) -> str:
    if identity_risk >= 0.60:
        score = min(1.0, score + 0.10)

    block = snap.block_threshold if snap else 0.80
    throttle = snap.throttle_threshold if snap else 0.55
    flag = snap.flag_threshold if snap else 0.25

    if score >= block:
        return "block"

    if score >= throttle:
        return "throttle"

    if score >= flag:
        return "flag"

    return "allow"
