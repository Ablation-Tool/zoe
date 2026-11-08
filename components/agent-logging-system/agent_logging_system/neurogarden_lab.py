"""Small educational instruments derived from cited Neurogarden reading.

Alignment scores and sampling ratios are not identity, diagnostic, or clinical
claims. Source references are preserved in each result.
"""
from dataclasses import dataclass
from functools import lru_cache
import math
from typing import List, Tuple


@dataclass(frozen=True)
class AlignmentResult:
    score: int
    alignments: List[Tuple[str, str]]
    truncated: bool
    source: str = "Basic Applied Bioinformatics, chapter 9, sections 9.1-9.3.4"
    clinical_claim: bool = False


def global_align(
    first: str, second: str, match: int = 2, mismatch: int = -1, gap: int = -2,
    max_length: int = 64, max_alignments: int = 128,
) -> AlignmentResult:
    if not 1 <= max_length <= 256 or not 1 <= max_alignments <= 4096:
        raise ValueError("invalid alignment bounds")
    if not isinstance(first, str) or not isinstance(second, str) \
            or not first or not second or len(first) > max_length or len(second) > max_length:
        raise ValueError("sequences must be nonempty and within the length bound")
    first = first.upper()
    second = second.upper()
    if not first.isalpha() or not second.isalpha():
        raise ValueError("sequences must contain letters only")
    if not isinstance(match, int) or not isinstance(mismatch, int) or not isinstance(gap, int) \
            or match <= 0 or mismatch > 0 or gap > 0:
        raise ValueError("require match > 0, mismatch <= 0, and gap <= 0")

    rows = len(first) + 1
    columns = len(second) + 1
    scores = [[0] * columns for _ in range(rows)]
    for row in range(1, rows):
        scores[row][0] = row * gap
    for column in range(1, columns):
        scores[0][column] = column * gap
    for row in range(1, rows):
        for column in range(1, columns):
            substitution = match if first[row - 1] == second[column - 1] else mismatch
            scores[row][column] = max(
                scores[row - 1][column - 1] + substitution,
                scores[row - 1][column] + gap,
                scores[row][column - 1] + gap,
            )

    truncated = False

    @lru_cache(maxsize=None)
    def paths(row: int, column: int):
        nonlocal truncated
        if row == 0 and column == 0:
            return [(("", ""), False)]
        candidates = []
        if row and column:
            substitution = match if first[row - 1] == second[column - 1] else mismatch
            candidates.append((scores[row - 1][column - 1] + substitution, "diagonal"))
        if row:
            candidates.append((scores[row - 1][column] + gap, "up"))
        if column:
            candidates.append((scores[row][column - 1] + gap, "left"))
        best = scores[row][column]
        results = []
        for score, direction in candidates:
            if score != best:
                continue
            previous_row = row - 1 if direction in {"diagonal", "up"} else row
            previous_column = column - 1 if direction in {"diagonal", "left"} else column
            for (left, right), was_truncated in paths(previous_row, previous_column):
                if direction == "diagonal":
                    pair = (left + first[row - 1], right + second[column - 1])
                elif direction == "up":
                    pair = (left + first[row - 1], right + "-")
                else:
                    pair = (left + "-", right + second[column - 1])
                if len(results) >= max_alignments:
                    truncated = True
                    break
                results.append((pair, was_truncated))
            if len(results) >= max_alignments:
                truncated = True
                break
        return results

    raw_paths = paths(rows - 1, columns - 1)
    alignments = []
    for (left, right), was_truncated in raw_paths:
        if was_truncated:
            truncated = True
        alignments.append((left, right))
    return AlignmentResult(scores[-1][-1], alignments, truncated)


@dataclass(frozen=True)
class SamplingAssessment:
    samples_per_fwhm: float
    tolerable: bool
    generally_good: bool
    source: str = "Biomedical Imaging Principles, chapter 2, section 2.3"
    clinical_claim: bool = False


def assess_sampling(fwhm_mm: float, pixel_size_mm: float) -> SamplingAssessment:
    if not 0 < fwhm_mm <= 1e6 or not 0 < pixel_size_mm <= 1e6:
        raise ValueError("FWHM and pixel size must be positive and bounded")
    ratio = fwhm_mm / pixel_size_mm
    return SamplingAssessment(ratio, ratio >= 2, ratio >= 4)


def gaussian_mtf(sigma_mm: float, frequency_cycles_per_mm: float) -> float:
    if not 0 < sigma_mm <= 1e6 or not 0 <= frequency_cycles_per_mm <= 1e9:
        raise ValueError("sigma must be positive and spatial frequency must be nonnegative and bounded")
    return math.exp(-2 * math.pi ** 2 * sigma_mm ** 2 * frequency_cycles_per_mm ** 2)


@dataclass(frozen=True)
class SafetyReview:
    topic: str
    checks: Tuple[str, ...]
    sources: Tuple[str, ...]
    review_required: bool = True
    clinical_action_authorized: bool = False


def mri_review() -> SafetyReview:
    return SafetyReview(
        "MRI",
        (
            "Static-field projectile and implant review before entering controlled areas",
            "RF-specific absorption rate and local heating review",
            "Gradient-induced nerve stimulation and acoustic-noise review",
            "Artifact, motion, and high-field inhomogeneity review",
        ),
        ("Biomedical Imaging Principles, chapter 5, sections 5.14-5.15",),
    )


def xray_review() -> SafetyReview:
    return SafetyReview(
        "X-ray",
        (
            "Dose-area product and tissue-specific context before effective-dose interpretation",
            "Detector, procedure, and staff-position dose-geometry review",
            "Protective-equipment and primary/scattered-beam review",
            "Jurisdiction-specific limits require current qualified review",
        ),
        ("Biomedical Imaging Principles, chapter 3, section 3.4",),
    )


def photon_counting_review() -> SafetyReview:
    return SafetyReview(
        "Photon-counting detectors",
        (
            "Energy-window and spectral-response validation",
            "Pulse pileup, dead-time count loss, and spectral-distortion review",
            "Charge sharing, trapping, and incomplete charge-collection review",
            "Compensation methods require validation rather than presumed superiority",
        ),
        ("Radiation Detectors for Medical Imaging, preface",),
    )


def chemical_review() -> SafetyReview:
    return SafetyReview(
        "Chemical safety",
        (
            "Identify the exact chemical and product and consult the current supplier SDS",
            "Review GHS pictograms and hazard statements without treating NFPA ratings as exposure limits",
            "Select glove material, thickness, and other PPE through SDS compatibility and qualified risk assessment",
            "Review ventilation, segregation, waste, and emergency plans under current local requirements",
            "Do not extrapolate animal LD50 values into human doses",
        ),
        ("BioCoder 4, Chemical Safety in DIYbio",),
    )


def ai_risk_review() -> SafetyReview:
    return SafetyReview(
        "Generative AI deployment",
        (
            "Evaluate biased and toxic outputs across affected groups; high-stakes medical, legal, or safety advice requires domain validation",
            "Require provenance, factual review, and synthetic-content disclosure; fluency is not evidence",
            "Minimize personal data and document retention, consent, access, and deletion",
            "Measure training and inference energy across the full model lifecycle",
            "Use private beta, gradual rollout, human review, and a tested stop/recovery path",
        ),
        ("GPT-3, chapter 6, risk and mitigation review",),
    )


def post_quantum_pairing_review():
    return {
        "post_quantum_ready": False,
        "current_vulnerable_algorithms": ["X25519", "Ed25519", "RSA-3072"],
        "qkd_is_not_pqc": True,
        "qkd_limitations": [
            "authenticated source still requires asymmetric cryptography or preplaced keys",
            "special-purpose hardware, distance, loss, and trusted-relay costs",
            "hardware imperfections, validation difficulty, and side channels",
            "denial-of-service risk and limited upgrade paths",
        ],
        "research_path": [
            "evaluate hybrid X25519 + ML-KEM session establishment",
            "evaluate hybrid Ed25519 + ML-DSA identity and author signatures",
            "test downgrade handling, payload bounds, side channels, and transcript verification",
        ],
        "algorithm_sources": {
            "ML-KEM": "https://csrc.nist.gov/pubs/fips/203/final",
            "ML-DSA": "https://csrc.nist.gov/pubs/fips/204/final",
            "SLH-DSA": "https://csrc.nist.gov/pubs/fips/205/final",
        },
        "qkd_source": "https://www.nsa.gov/Cybersecurity/Quantum-Key-Distribution-QKD-and-Quantum-Cryptography-QC/",
        "migration_implemented": False,
        "qkd_deployed": False,
        "network_called": False,
        "clinical_claim": False,
    }


@dataclass(frozen=True)
class ReadPlan:
    fragment_length_bases: int
    read_length_bases: int
    overlap_bases: int
    bidirectional_recommended: bool
    source: str = "BioCoder 4, Fun and Fights with Fungi, Part 2"
    idealized: bool = True
    clinical_claim: bool = False


def bidirectional_read_plan(fragment_length_bases: int, read_length_bases: int) -> ReadPlan:
    if not isinstance(fragment_length_bases, int) or isinstance(fragment_length_bases, bool) \
            or not isinstance(read_length_bases, int) or isinstance(read_length_bases, bool) \
            or not 1 <= fragment_length_bases <= 100_000 or not 1 <= read_length_bases <= 100_000:
        raise ValueError("fragment and read lengths must be integers from 1 to 100000 bases")
    overlap = min(fragment_length_bases, max(0, 2 * read_length_bases - fragment_length_bases))
    return ReadPlan(
        fragment_length_bases,
        read_length_bases,
        overlap,
        read_length_bases < fragment_length_bases,
    )


@dataclass(frozen=True)
class TranslationRatio:
    value: float
    median_rna_intensity: float
    source: str = "BioCoder 2, Molecular Tools for Synthetic Biology in Plants"
    exploratory: bool = True
    clinical_claim: bool = False


def translation_ratio(protein_abundance: float, rna_intensities) -> TranslationRatio:
    if not 1 <= len(rna_intensities) <= 4096:
        raise ValueError("RNA intensities require 1 to 4096 values")
    protein = float(protein_abundance)
    values = [float(value) for value in rna_intensities]
    if not math.isfinite(protein) or protein <= 0 \
            or any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("protein abundance and RNA intensities must be finite and positive")
    values.sort()
    midpoint = len(values) // 2
    median = values[midpoint] if len(values) % 2 else (values[midpoint - 1] + values[midpoint]) / 2
    return TranslationRatio(protein / median, median)


@dataclass(frozen=True)
class PromptPlan:
    prompt_sha256: str
    characters: int
    response_length: int
    estimated_prompt_tokens: int
    estimated_total_tokens: int
    within_historical_budget: bool
    temperature: float
    top_p: float
    historical_budget_tokens: int = 2048
    actual_tokenizer_used: bool = False
    network_called: bool = False
    clinical_claim: bool = False
    source: str = "GPT-3, chapter 2, historical token approximation and parameter ranges"


def offline_prompt_plan(prompt, response_length=128, temperature=0.0, top_p=1.0):
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 16_000:
        raise ValueError("prompt must contain 1 to 16000 characters")
    if not isinstance(response_length, int) or isinstance(response_length, bool) \
            or not 1 <= response_length <= 2048:
        raise ValueError("response length must be an integer from 1 to 2048")
    if not isinstance(temperature, (int, float)) or isinstance(temperature, bool) \
            or not isinstance(top_p, (int, float)) or isinstance(top_p, bool) \
            or not math.isfinite(temperature) or not math.isfinite(top_p) \
            or not 0 <= temperature <= 1 or not 0 <= top_p <= 1:
        raise ValueError("temperature and top_p must be finite values in [0, 1]")
    import hashlib
    estimated_prompt_tokens = math.ceil(len(prompt) / 4)
    estimated_total_tokens = estimated_prompt_tokens + response_length
    return PromptPlan(
        hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        len(prompt),
        response_length,
        estimated_prompt_tokens,
        estimated_total_tokens,
        estimated_total_tokens <= 2048,
        float(temperature),
        float(top_p),
    )


def programming_request_review(
    prompt, engine="davinci", response_length=100, temperature=0.5,
    top_p=1.0, frequency_penalty=0.2, stop_sequences=("\n\n",),
):
    import re
    if isinstance(prompt, str) and re.search(r"\bsk-[A-Za-z0-9_-]{16,}\b", prompt):
        raise ValueError("credential-shaped prompt content is not accepted")
    if engine not in {"davinci", "curie", "babbage", "ada"}:
        raise ValueError("engine must be one of the four historical examples")
    if not isinstance(stop_sequences, (list, tuple)) or len(stop_sequences) > 4 \
            or any(not isinstance(value, str) or not 1 <= len(value) <= 128 for value in stop_sequences):
        raise ValueError("stop sequences must contain at most four short strings")
    if not isinstance(frequency_penalty, (int, float)) or isinstance(frequency_penalty, bool) \
            or not math.isfinite(frequency_penalty) or abs(frequency_penalty) > 2:
        raise ValueError("frequency penalty must be finite and bounded")
    plan = offline_prompt_plan(prompt, response_length, temperature, top_p)
    return {
        "engine": engine,
        "prompt_plan": plan,
        "frequency_penalty": float(frequency_penalty),
        "stop_sequences": list(stop_sequences),
        "historical_example": True,
        "credential_scan": "limited to common OpenAI-key-shaped strings",
        "credentials_embedded": False,
        "network_called": False,
        "library_installed": False,
        "source": "GPT-3, chapter 3, offline programming-request review",
        "clinical_claim": False,
    }


def complex_integer_power(real, imaginary, exponent):
    if not isinstance(real, int) or isinstance(real, bool) \
            or not isinstance(imaginary, int) or isinstance(imaginary, bool) \
            or abs(real) > 1_000_000 or abs(imaginary) > 1_000_000:
        raise ValueError("complex components must be bounded integers")
    if not isinstance(exponent, int) or isinstance(exponent, bool) or not 0 <= exponent <= 64:
        raise ValueError("exponent must be an integer from 0 to 64")
    result_real, result_imaginary = 1, 0
    for _ in range(exponent):
        result_real, result_imaginary = (
            result_real * real - result_imaginary * imaginary,
            result_real * imaginary + result_imaginary * real,
        )
    return {
        "real": result_real,
        "imaginary": result_imaginary,
        "multiplications": exponent,
        "exact": True,
        "source": "MATLAB Numerical Calculations, chapter 1, exact integer-complex arithmetic",
        "clinical_claim": False,
    }
