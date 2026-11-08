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
