import pytest

from agent_logging_system.neurogarden_lab import (
    assess_sampling, bidirectional_read_plan, chemical_review, gaussian_mtf, global_align,
    mri_review, offline_prompt_plan, photon_counting_review, programming_request_review,
    translation_ratio, xray_review,
)


def alignment_score(first, second):
    score = 0
    for left, right in zip(first, second):
        if left == "-" or right == "-":
            score -= 2
        else:
            score += 2 if left == right else -1
    return score


def test_book_alignment_has_score_four_and_seven_optimal_paths():
    result = global_align("CTAGTAG", "CAGGTAGTG")
    assert result.score == 4
    assert len(result.alignments) == 7
    assert not result.truncated
    assert not result.clinical_claim
    for first, second in result.alignments:
        assert len(first) == len(second)
        assert alignment_score(first, second) == 4


def test_identical_sequences_have_one_optimal_alignment():
    result = global_align("ACGT", "ACGT")
    assert result.score == 8
    assert result.alignments == [("ACGT", "ACGT")]


def test_alignment_bounds_and_schemes_are_validated():
    with pytest.raises(ValueError):
        global_align("", "AC")
    with pytest.raises(ValueError):
        global_align("AC1", "ACT")
    with pytest.raises(ValueError):
        global_align("AC", "AC", match=0)
    with pytest.raises(ValueError):
        global_align("AAAA", "AA", max_alignments=0)


def test_alignment_enumeration_is_bounded():
    result = global_align("CTAGTAG", "CAGGTAGTG", max_alignments=4)
    assert len(result.alignments) <= 4
    assert result.truncated
    assert all(alignment_score(first, second) == 4 for first, second in result.alignments)


def test_sampling_preserves_the_resolution_voxel_distinction():
    assessment = assess_sampling(4, 1)
    assert assessment.samples_per_fwhm == 4
    assert assessment.tolerable and assessment.generally_good
    assert not assessment.clinical_claim
    assert assess_sampling(4, 3).samples_per_fwhm == pytest.approx(4 / 3)
    assert not assess_sampling(4, 3).tolerable
    with pytest.raises(ValueError):
        assess_sampling(0, 1)


def test_gaussian_mtf_matches_normalized_fourier_magnitude():
    assert gaussian_mtf(1, 0) == 1
    assert gaussian_mtf(1, 1) == pytest.approx(2.675287991074243e-9, rel=1e-12)
    assert gaussian_mtf(1, 0.5) > gaussian_mtf(1, 1)
    with pytest.raises(ValueError):
        gaussian_mtf(0, 1)


def test_safety_reviews_are_sourced_and_never_authorize_action():
    for review in (mri_review(), xray_review(), photon_counting_review()):
        assert review.review_required
        assert not review.clinical_action_authorized
        assert review.sources
        assert len(review.checks) == 4
    assert "projectile" in mri_review().checks[0]
    assert "pileup" in photon_counting_review().checks[1]


def test_chemical_review_requires_current_sds_not_human_dose_extrapolation():
    review = chemical_review()
    assert review.review_required
    assert not review.clinical_action_authorized
    assert "current supplier SDS" in review.checks[0]
    assert "Do not extrapolate animal LD50 values into human doses" in review.checks


def test_bidirectional_read_plan_is_idealized_sequence_geometry():
    plan = bidirectional_read_plan(800, 650)
    assert plan.overlap_bases == 500
    assert plan.bidirectional_recommended
    assert plan.idealized
    assert not plan.clinical_claim
    single = bidirectional_read_plan(800, 800)
    assert single.overlap_bases == 800
    assert not single.bidirectional_recommended
    with pytest.raises(ValueError):
        bidirectional_read_plan(0, 650)
    with pytest.raises(ValueError):
        bidirectional_read_plan(800, 650.5)


def test_translation_ratio_uses_median_and_remains_exploratory():
    result = translation_ratio(4, [1, 3, 2])
    assert result.value == 2
    assert result.median_rna_intensity == 2
    assert result.exploratory
    assert not result.clinical_claim
    assert translation_ratio(4, [1, 3]).value == 2
    with pytest.raises(ValueError):
        translation_ratio(4, [])
    with pytest.raises(ValueError):
        translation_ratio(4, [1, 0, 2])
    with pytest.raises(ValueError):
        translation_ratio(4, [1, float("nan"), 2])


def test_offline_prompt_plan_estimates_budget_without_calling_a_model():
    plan = offline_prompt_plan("abcdefghijklmnop", response_length=4, temperature=0.2)
    assert plan.estimated_prompt_tokens == 4
    assert plan.estimated_total_tokens == 8
    assert plan.within_historical_budget
    assert plan.temperature == 0.2
    assert plan.top_p == 1
    assert not plan.actual_tokenizer_used
    assert not plan.network_called
    assert not plan.clinical_claim
    assert "abcdefghijklmnop" not in repr(plan)
    assert offline_prompt_plan("x" * 9000, response_length=100).within_historical_budget is False
    with pytest.raises(ValueError):
        offline_prompt_plan("valid", response_length=0)
    with pytest.raises(ValueError):
        offline_prompt_plan("valid", temperature=-0.1)
    with pytest.raises(ValueError):
        offline_prompt_plan("valid", top_p=1.1)
    with pytest.raises(ValueError):
        offline_prompt_plan("x" * 16001)


def test_programming_request_review_is_offline_and_rejects_credentials():
    review = programming_request_review("Summarize this synthetic paragraph")
    assert review["engine"] == "davinci"
    assert review["prompt_plan"].response_length == 100
    assert review["stop_sequences"] == ["\n\n"]
    assert review["historical_example"]
    assert not review["credentials_embedded"]
    assert not review["network_called"]
    assert not review["library_installed"]
    assert not review["clinical_claim"]
    assert "Summarize this synthetic paragraph" not in repr(review)
    with pytest.raises(ValueError, match="credential-shaped"):
        programming_request_review("sk-example1234567890abcdef")
    with pytest.raises(ValueError):
        programming_request_review("valid", engine="unsupported")
    with pytest.raises(ValueError):
        programming_request_review("valid", stop_sequences=["a", "b", "c", "d", "e"])
