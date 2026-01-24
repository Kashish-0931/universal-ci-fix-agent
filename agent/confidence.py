def compute_confidence(validated: bool, files_changed: int):
    score = 0.0

    if validated:
        score += 0.5

    if files_changed == 1:
        score += 0.3
    elif files_changed <= 3:
        score += 0.15

    score += 0.2  # error resolved

    return round(min(score, 1.0), 2)
