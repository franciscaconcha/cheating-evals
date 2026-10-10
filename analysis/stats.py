"""Small statistics helpers: Wilson intervals, agreement and Cohen's kappa."""

import math
from collections import Counter


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def agreement(a: list, b: list) -> float:
    return sum(x == y for x, y in zip(a, b)) / len(a)


def cohen_kappa(a: list, b: list) -> float | None:
    """Cohen's kappa; None when undefined (both raters use a single identical label)."""
    n = len(a)
    po = agreement(a, b)
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n**2
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def confusion(a: list, b: list) -> dict[tuple, int]:
    return Counter(zip(a, b))
