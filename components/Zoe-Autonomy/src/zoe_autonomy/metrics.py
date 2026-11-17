from __future__ import annotations

import math


DEFAULT_THRESHOLDS = (.02, .05, .10, .15, .30, .50)
MAX_DISTRIBUTION_SIZE = 4096
MAX_ACCESSIBLE_INTERVENTIONS = 256
DIMENSIONS = (
    "effective_perception_coverage",
    "internal_proposal_ratio",
    "state_responsiveness",
    "value_based_selection_ratio",
    "internal_goal_authorship_ratio",
    "internally_authorized_execution_ratio",
    "guard_compliance",
)


def probability(value, label="probability", *, endpoints=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    lower_ok = 0 <= result if endpoints else 0 < result
    if not lower_ok or result > 1:
        raise ValueError(f"{label} must be in {'[0, 1]' if endpoints else '(0, 1]'}")
    return result


def nonnegative(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return float(value)


def distribution(values, label="distribution"):
    if not isinstance(values, dict) or not 1 <= len(values) <= MAX_DISTRIBUTION_SIZE:
        raise ValueError(f"{label} must contain 1-{MAX_DISTRIBUTION_SIZE} labeled probabilities")
    result = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip() or len(key) > 256:
            raise ValueError(f"{label} labels must contain 1-256 characters")
        result[key] = probability(value, f"{label} probability")
    if not math.isclose(sum(result.values()), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"{label} probabilities must sum to one within 1e-9")
    return result


def accessible_volume(probabilities, tau):
    values = list(probabilities)
    if not 1 <= len(values) <= MAX_DISTRIBUTION_SIZE:
        raise ValueError(f"probabilities must contain 1-{MAX_DISTRIBUTION_SIZE} values")
    values = [probability(value) for value in values]
    if not math.isclose(sum(values), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("probabilities must sum to one within 1e-9")
    tau = probability(tau, "tau", endpoints=False)
    return sum(value > tau for value in values)


def threshold_sweep(probabilities, thresholds=DEFAULT_THRESHOLDS):
    values = list(probabilities)
    return [
        {"tau": probability(tau, "tau", endpoints=False), "accessible_volume": accessible_volume(values, tau)}
        for tau in thresholds
    ]


def kl_divergence_bits(intervened, baseline):
    intervened = distribution(intervened, "intervened policy")
    baseline = distribution(baseline, "baseline policy")
    if set(intervened) != set(baseline):
        raise ValueError("baseline and intervened policies must share one finite action vocabulary")
    result = 0.0
    for action, value in intervened.items():
        reference = baseline[action]
        if value == 0:
            continue
        if reference == 0:
            return {"divergence_bits": None, "infinite": True, "support_mismatch": True}
        result += value * math.log2(value / reference)
    if result < 0 and abs(result) < 1e-12:
        result = 0.0
    if result < 0 or not math.isfinite(result):
        raise ValueError("KL divergence calculation failed")
    return {"divergence_bits": result, "infinite": False, "support_mismatch": False}


def effective_perception(forecast, baseline_policy, intervened_policies, tau=.05, delta=.001):
    forecast = distribution(forecast, "forecast")
    baseline_policy = distribution(baseline_policy, "baseline policy")
    if not isinstance(intervened_policies, dict):
        raise ValueError("intervened policies must be a mapping")
    tau = probability(tau, "tau", endpoints=False)
    delta = nonnegative(delta, "delta")
    accessible = sorted(token for token, value in forecast.items() if value > tau)
    if len(accessible) > MAX_ACCESSIBLE_INTERVENTIONS:
        raise ValueError(f"accessible intervention set exceeds {MAX_ACCESSIBLE_INTERVENTIONS} cases")
    if set(accessible) - set(intervened_policies):
        raise ValueError("every accessible alternative requires an explicit intervened policy")
    records = []
    effective = 0
    for token in accessible:
        policy = distribution(intervened_policies[token], f"intervention {token}")
        effect = kl_divergence_bits(policy, baseline_policy)
        selected = effect["infinite"] or effect["divergence_bits"] > delta
        effective += int(selected)
        records.append({
            "intervention": token,
            "forecast_probability": forecast[token],
            **effect,
            "effective": selected,
        })
    volume = len(accessible)
    return {
        "tau": tau,
        "delta": delta,
        "divergence_units": "bits",
        "accessible_volume": volume,
        "effective_perception_count": effective,
        "effective_perception_coverage": effective / volume if volume else None,
        "infinite_divergence_count": sum(record["infinite"] for record in records),
        "interventions": records,
        "equation": "P_tau,delta = sum_z 1[p(z)>tau] 1[D_KL(pi(a|do(z),c)||pi(a|c))>delta]",
    }


def dimensions(values):
    if not isinstance(values, dict) or set(values) != set(DIMENSIONS):
        raise ValueError("profile dimensions must exactly cover the declared autonomy profile")
    result = {}
    for name in DIMENSIONS:
        value = values[name]
        if name == "effective_perception_coverage" and value is None:
            result[name] = None
        else:
            result[name] = probability(value, name)
    return result


def classify(values):
    values = dimensions(values)
    if values["guard_compliance"] < 1:
        return "guard_failure"
    deliberative = values["internal_proposal_ratio"] > 0 and values["state_responsiveness"] > 0
    executive = (
        deliberative
        and values["value_based_selection_ratio"] > 0
        and values["internally_authorized_execution_ratio"] > 0
    )
    if executive and values["internal_goal_authorship_ratio"] > 0:
        return "full_autonomy"
    if executive:
        return "bounded_means_autonomy"
    if deliberative:
        return "proposal_level_bounded_agency"
    return "forecast_or_external_control_only"


def profile(accessible_count, values):
    if isinstance(accessible_count, bool) or not isinstance(accessible_count, int) or accessible_count < 0:
        raise ValueError("accessible_count must be a nonnegative integer")
    values = dimensions(values)
    coverage = values["effective_perception_coverage"]
    diagnostic = None
    if coverage is not None:
        diagnostic = (
            values["internal_proposal_ratio"]
            * values["state_responsiveness"]
            * coverage
        ) ** (1 / 3)
    return {
        "accessible_volume": accessible_count,
        "dimensions": values,
        "classification": classify(values),
        "deliberative_diagnostic": diagnostic,
        "diagnostic_scope": "The geometric mean covers only I, R, and E. The complete vector and classification are primary; the diagnostic is not a universal autonomy score.",
    }
