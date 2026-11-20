"""Deterministic summaries of Bell measurements, independent of the simulator."""

from math import isfinite, sqrt
from statistics import median, quantiles


WORDS = ("00", "01", "10", "11")
EXPECTED = {
    "ideal": {"00": 0.5, "01": 0.0, "10": 0.0, "11": 0.5},
    "readout_2pct": {"00": 0.4804, "01": 0.0196, "10": 0.0196, "11": 0.4804},
}


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


def _counts(value, shots):
    if not isinstance(value, dict) or any(word not in WORDS for word in value):
        raise ValueError("counts must map two-bit Bell outcomes to integers")
    # Aer can omit outcomes with zero observations.
    counts = {word: _integer(value.get(word, 0), "count", 0) for word in WORDS}
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


def summarize(attempts: list[dict], shots: int, repetitions: int) -> dict:
    """Validate an attempt log and aggregate only completed measured repetitions.

    Times are milliseconds. The interval [q1, q3] uses inclusive, linearly
    interpolated quartiles. With one observation both quartiles are that time.
    TVD is measured against ideal Bell for *both* experimental conditions.
    """
    _integer(shots, "shots", 1)
    _integer(repetitions, "repetitions", 1)
    if not isinstance(attempts, list):
        raise ValueError("attempts must be a list")

    seen_attempts = set()
    seen_successes = set()
    counts_by_condition = {condition: dict.fromkeys(WORDS, 0) for condition in EXPECTED}
    durations = {condition: [] for condition in EXPECTED}
    failures = dict.fromkeys(EXPECTED, 0)
    for record in attempts:
        if not isinstance(record, dict):
            raise ValueError("attempt entries must be objects")
        condition = record.get("condition")
        if not isinstance(condition, str) or condition not in EXPECTED:
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

        counts = _counts(record.get("counts"), shots)
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
        valid = counts["00"] + counts["11"]
        quartiles = None
        if len(times) == 1:
            quartiles = [times[0], times[0]]
        elif len(times) > 1:
            q1, _, q3 = quantiles(times, n=4, method="inclusive")
            quartiles = [q1, q3]
        # Express the ideal reference in integer half-count units to avoid
        # cancellation for almost perfectly balanced finite samples.
        tvd = None
        if total:
            tvd = (
                abs(2 * counts["00"] - total) + 2 * counts["01"]
                + 2 * counts["10"] + abs(2 * counts["11"] - total)
            ) / (4 * total)
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
