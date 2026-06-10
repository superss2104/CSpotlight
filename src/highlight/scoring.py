def normalize_scores(scores):
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [0.0 for _ in scores]

    span = max_score - min_score
    return [(score - min_score) / span for score in scores]


def combine_scores(primary_scores, secondary_scores, primary_weight=0.65, secondary_weight=0.35):
    if not primary_scores:
        return []
    if not secondary_scores:
        return normalize_scores(primary_scores)

    normalized_primary = normalize_scores(primary_scores)
    normalized_secondary = normalize_scores(secondary_scores)
    combined = []

    for idx, primary_score in enumerate(normalized_primary):
        if idx < len(normalized_secondary):
            secondary_score = normalized_secondary[idx]
        else:
            secondary_score = 0.0
        combined.append(primary_weight * primary_score + secondary_weight * secondary_score)

    return combined
