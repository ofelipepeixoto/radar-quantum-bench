"""Analytic references and deterministic summaries independent of the simulator."""

from math import isfinite, sqrt
from statistics import median, quantiles


_CIRCUITS = {
    # Label, total qubits, equiprobable ideal measurement outcomes.
    "bell": ("Bell", 2, ("00", "11")),
    "ghz": ("GHZ", 3, ("000", "111")),
    "bv": ("Bernstein-Vazirani", 4, ("110",)),
}
_CONDITIONS = ("ideal", "readout_2pct")


def specifications(circuit: str) -> dict:
    """Describe a circuit and its output with independent 2% flips on measured bits."""
    if not isinstance(circuit, str) or circuit not in _CIRCUITS:
        raise ValueError(f"unknown circuit: {circuit!r}")
    label, qubits, support = _CIRCUITS[circuit]
    measured = len(support[0])
    words = tuple(format(index, f"0{measured}b") for index in range(2**measured))
    ideal = {word: 1 / len(support) if word in support else 0.0 for word in words}

    # A bit stays unchanged with probability 49/50 and flips with probability
    # 1/50. Accumulate the integer numerators over the uniform ideal support.
    denominator = len(support) * 50**measured
    noisy = {}
    for word in words:
        weight = 0
        for source in support:
            unchanged = sum(a == b for a, b in zip(source, word))
            weight += 49**unchanged
        noisy[word] = weight / denominator
    return {"words": words, "ideal": ideal, "noisy": noisy, "qubits": qubits,
            "measured": measured, "label": label}


def theoretical_probabilities(circuit: str) -> dict:
    spec = specifications(circuit)
    return {"ideal": spec["ideal"], "readout_2pct": spec["noisy"]}


# Original names retained for callers that read Bell version 1 results.
EXPECTED = theoretical_probabilities("bell")
WORDS = tuple(EXPECTED["ideal"])


def _integer(value, name, minimum):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _duration(value):
    if type(value) not in (int, float) or value < 0:
        raise ValueError("elapsed_ms must be a finite, nonnegative duration")
    try:
        finite = isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("elapsed_ms must be a finite, nonnegative duration")
    return float(value)


def _counts(value, shots, words):
    if not isinstance(value, dict) or any(word not in words for word in value):
        raise ValueError("counts must map outcomes of the selected circuit to integers")
    # Aer can omit outcomes with zero observations.
    counts = {word: _integer(value.get(word, 0), "count", 0) for word in words}
    if sum(counts.values()) != shots:
        raise ValueError("counts do not add up to shots")
    return counts


def _wilson95(successes, total):
    z = 1.959963984540054
    fraction = successes / total
    denominator = 1 + z**2 / total
    midpoint = (fraction + z**2 / (2 * total)) / denominator
    half_width = z * sqrt(fraction * (1 - fraction) / total + z**2 / (4 * total**2)) / denominator
    lower = 0.0 if successes == 0 else max(0.0, midpoint - half_width)
    upper = 1.0 if successes == total else min(1.0, midpoint + half_width)
    return [lower, upper]


def summarize(attempts: list[dict], shots: int, repetitions: int, circuit: str = "bell") -> dict:
    """Validate an attempt log and aggregate only completed measured repetitions.

    Times are milliseconds. The interval [q1, q3] uses inclusive, linearly
    interpolated quartiles. With one observation both quartiles are that time.
    TVD is measured against the selected ideal reference for both conditions.
    """
    _integer(shots, "shots", 1)
    _integer(repetitions, "repetitions", 1)
    if not isinstance(attempts, list):
        raise ValueError("attempts must be a list")

    spec = specifications(circuit)
    words = spec["words"]
    support = {word for word in words if spec["ideal"][word] > 0}
    support_size = len(support)
    seen_attempts = set()
    seen_successes = set()
    counts_by_condition = {condition: dict.fromkeys(words, 0) for condition in _CONDITIONS}
    durations = {condition: [] for condition in _CONDITIONS}
    failures = dict.fromkeys(_CONDITIONS, 0)
    for record in attempts:
        if not isinstance(record, dict):
            raise ValueError("attempt entries must be objects")
        condition = record.get("condition")
        if not isinstance(condition, str) or condition not in _CONDITIONS:
            raise ValueError("unknown condition")
        status = record.get("status")
        if status not in ("ok", "failed", "running"):
            raise ValueError("unknown attempt status")
        warmup = record.get("warmup")
        if type(warmup) is not bool:
            raise ValueError("warmup must be a boolean")
        repetition = _integer(record.get("repetition"), "repetition", -1)
        if warmup != (repetition == -1) or repetition >= repetitions:
            raise ValueError("repetition outside configured range or invalid warmup")
        attempt = _integer(record.get("attempt"), "attempt", 1)
        _integer(record.get("seed"), "seed", 0)
        repetition_id = (condition, repetition)
        attempt_id = (condition, repetition, attempt)
        if attempt_id in seen_attempts:
            raise ValueError(f"duplicate attempt {attempt_id}")
        seen_attempts.add(attempt_id)

        elapsed = record.get("elapsed_ms")
        if elapsed is not None or status == "ok":
            elapsed = _duration(elapsed)
        if status != "ok":
            if status == "failed" and not warmup:
                failures[condition] += 1
            continue

        counts = _counts(record.get("counts"), shots, words)
        if repetition_id in seen_successes:
            raise ValueError(f"multiple successful attempts for {repetition_id}")
        seen_successes.add(repetition_id)
        if not warmup:
            durations[condition].append(elapsed)
            for word, count in counts.items():
                counts_by_condition[condition][word] += count

    conditions = {}
    for condition, counts in counts_by_condition.items():
        times = durations[condition]
        total = sum(counts.values())
        valid = sum(counts[word] for word in support)
        quartiles = None
        if len(times) == 1:
            quartiles = [times[0], times[0]]
        elif len(times) > 1:
            q1, _, q3 = quantiles(times, n=4, method="inclusive")
            quartiles = [q1, q3]
        # Expected probability is 1/support_size for each word in support.
        # Work in integer units and round only once, at the final division.
        tvd = None
        if total:
            deviation = sum(
                abs(support_size * count - (total if word in support else 0))
                for word, count in counts.items()
            )
            tvd = deviation / (2 * support_size * total)
        conditions[condition] = {
            "counts": counts,
            "total_shots": total,
            "valid_shots": valid,
            "valid_fraction": valid / total if total else None,
            "wilson95": _wilson95(valid, total) if total else None,
            "tvd": tvd,
            "completed_repetitions": len(times),
            "failed_attempts": failures[condition],
            "median_ms": median(times) if times else None,
            "quartiles_ms": quartiles,
            "iqr_ms": quartiles[1] - quartiles[0] if quartiles else None,
        }
    return {
        "complete": all(len(times) == repetitions for times in durations.values()),
        "total_shots": sum(row["total_shots"] for row in conditions.values()),
        "conditions": conditions,
    }
