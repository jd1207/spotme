RECOVERY_GREEN = 67
RECOVERY_YELLOW = 34


def recovery_zone(score: float | None) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= RECOVERY_GREEN:
        return "GREEN"
    if score >= RECOVERY_YELLOW:
        return "YELLOW"
    return "RED"
