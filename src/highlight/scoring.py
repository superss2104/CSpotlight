def normalize_scores(scores):
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return [0.0 for _ in scores]

    span = max_score - min_score
    return [(score - min_score) / span for score in scores]




def combine_multiple_scores(score_lists, weights):
    """Fuse *N* score signals with corresponding *weights*.

    Each signal is independently min-max normalized to ``[0, 1]``.  The first
    entry in *score_lists* is treated as the primary signal and determines the
    output length.  Shorter secondary signals are zero-padded.

    Returns an empty list when the primary signal is empty.
    """
    if not score_lists or not score_lists[0]:
        return []
    if len(score_lists) != len(weights):
        raise ValueError("score_lists and weights must have the same length")

    primary_length = len(score_lists[0])
    normalized = [normalize_scores(s) for s in score_lists]

    combined = []
    for idx in range(primary_length):
        value = 0.0
        for signal_idx, norm_signal in enumerate(normalized):
            if idx < len(norm_signal):
                value += weights[signal_idx] * norm_signal[idx]
        combined.append(value)

    return combined
