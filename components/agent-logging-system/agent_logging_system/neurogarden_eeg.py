"""Synthetic EEG/signal teaching methods from the cited signal-processing chapter."""
import math

SOURCE = "Computational Intelligence and Predictive Analysis for Medical Science, EEG analysis, pages 139-150"
DEFAULT_BANDS = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 7.0),
    "alpha": (7.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 100.0),
}


def validate_samples(samples, sample_rate):
    values = [float(value) for value in samples]
    if len(values) < 16 or len(values) > 4096 or any(not math.isfinite(value) for value in values):
        raise ValueError("samples must contain 16 to 4096 finite values")
    if not 0 < sample_rate <= 10_000:
        raise ValueError("sample rate must be positive and bounded")
    return values


def band_powers(samples, sample_rate, bands=None):
    values = validate_samples(samples, sample_rate)
    bands = bands or DEFAULT_BANDS
    nyquist = sample_rate / 2
    powers = {name: 0.0 for name in bands}
    total = 0.0
    for index in range(len(values) // 2 + 1):
        frequency = index * sample_rate / len(values)
        real = 0.0
        imaginary = 0.0
        for position, sample in enumerate(values):
            angle = 2 * math.pi * index * position / len(values)
            real += sample * math.cos(angle)
            imaginary -= sample * math.sin(angle)
        power = real * real + imaginary * imaginary
        total += power
        for name, (low, high) in bands.items():
            if low <= frequency < high and frequency <= nyquist:
                powers[name] += power
    if total <= 0:
        raise ValueError("signal has no spectral energy")
    return {name: value / total for name, value in powers.items()}


def delay_embed(samples, dimension=10, delay=1):
    values = validate_samples(samples, 1)
    if not 1 <= dimension <= 10 or not 1 <= delay <= len(values):
        raise ValueError("invalid embedding dimension or delay")
    if (dimension - 1) * delay >= len(values):
        raise ValueError("embedding exceeds the sample count")
    return [
        tuple(values[index - step * delay] for step in range(dimension))
        for index in range((dimension - 1) * delay, len(values))
    ]


def least_squares_slope(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("slope requires at least two points")
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((value - mean_x) ** 2 for value in xs)
    if denominator == 0:
        raise ValueError("slope is undefined for constant abscissa")
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denominator


def lyapunov_estimate(samples, dimension=10, delay=1):
    embedded = delay_embed(samples, dimension, delay)
    divergences = []
    for index, point in enumerate(embedded):
        distances = [
            math.dist(point, other)
            for other_index, other in enumerate(embedded)
            if other_index != index and abs(other_index - index) > delay
        ]
        if not distances:
            raise ValueError("no independent trajectory neighbor is available")
        nearest = min(distances)
        if nearest == 0:
            divergences.append(0.0)
        else:
            divergences.append(math.log(nearest))
    return least_squares_slope(list(range(len(divergences))), divergences)


def higuchi_dimension(samples, max_interval=None):
    values = validate_samples(samples, 1)
    count = len(values)
    max_interval = max_interval or min(8, count // 4)
    if not 1 <= max_interval <= count // 2:
        raise ValueError("invalid Higuchi interval bound")
    xs = []
    ys = []
    for interval in range(1, max_interval + 1):
        lengths = []
        for initial in range(1, interval + 1):
            steps = int((count - initial) / interval)
            if steps <= 0:
                continue
            length = sum(
                abs(values[initial + step * interval - 1] - values[initial + (step - 1) * interval - 1])
                for step in range(1, steps + 1)
            )
            lengths.append(length * (count - 1) / (steps * interval))
        if lengths and sum(lengths) > 0:
            xs.append(math.log(1 / interval))
            ys.append(math.log(sum(lengths) / len(lengths)))
    if len(xs) < 2:
        raise ValueError("Higuchi dimension requires nonzero curve lengths")
    return least_squares_slope(xs, ys)


def shannon_entropy(probabilities):
    values = [value for value in probabilities if value > 0]
    if not values or any(value < 0 for value in probabilities):
        raise ValueError("probabilities must be nonnegative")
    total = sum(values)
    if total <= 0:
        raise ValueError("probability mass must be positive")
    return -sum((value / total) * math.log2(value / total) for value in values)
