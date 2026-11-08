import pytest

from agent_logging_system.neurogarden_lab import (
    assess_sampling, bidirectional_read_plan, chemical_review, gaussian_mtf, global_align,
    ai_risk_review, mri_review, offline_prompt_plan, photon_counting_review, programming_request_review,
    complex_integer_power, post_quantum_pairing_review, translation_ratio, xray_review,
    gcd_lcm, binomial_coefficient, convert_base_number, divisor_summary,
    brain_tumor_validation_review,
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


def test_ai_risk_review_is_a_checklist_not_a_safety_score():
    review = ai_risk_review()
    assert review.review_required
    assert not review.clinical_action_authorized
    assert len(review.checks) == 5
    assert "fluency is not evidence" in review.checks[1]
    assert "full model lifecycle" in review.checks[3]
    assert "stop/recovery path" in review.checks[4]
    assert review.sources == ("GPT-3, chapter 6, risk and mitigation review",)


def test_complex_integer_power_reproduces_the_book_example_exactly():
    result = complex_integer_power(2, 3, 10)
    assert result["real"] == -341525
    assert result["imaginary"] == -145668
    assert result["multiplications"] == 10
    assert result["exact"]
    assert not result["clinical_claim"]
    assert complex_integer_power(2, 3, 0) == {
        "real": 1, "imaginary": 0, "multiplications": 0, "exact": True,
        "source": "MATLAB Numerical Calculations, chapter 1, exact integer-complex arithmetic",
        "clinical_claim": False,
    }
    with pytest.raises(ValueError):
        complex_integer_power(2, 3, -1)
    with pytest.raises(ValueError):
        complex_integer_power(2, 3, 65)
    with pytest.raises(ValueError):
        complex_integer_power(2.5, 3, 2)


def test_post_quantum_pairing_review_is_honest_about_current_limits():
    review = post_quantum_pairing_review()
    assert review["post_quantum_ready"] is False
    assert review["current_vulnerable_algorithms"] == ["X25519", "Ed25519", "RSA-3072"]
    assert review["qkd_is_not_pqc"]
    assert len(review["qkd_limitations"]) == 4
    assert "hybrid X25519 + ML-KEM" in review["research_path"][0]
    assert "hybrid Ed25519 + ML-DSA" in review["research_path"][1]
    assert review["algorithm_sources"]["ML-KEM"].endswith("203/final")
    assert review["algorithm_sources"]["ML-DSA"].endswith("204/final")
    assert review["algorithm_sources"]["SLH-DSA"].endswith("205/final")
    assert review["qkd_source"].endswith("quantum-cryptographic-solutions-are-limited-compared-to-post-quantum-algorithms/")
    assert "environmental degradation" in review["qkd_limitations"][2]
    assert not review["migration_implemented"]
    assert not review["qkd_deployed"]
    assert not review["network_called"]
    assert not review["clinical_claim"]


def test_integer_toolkit_reproduces_chapter_two_examples():
    assert gcd_lcm([1000, 500, 625])["gcd"] == 125
    assert gcd_lcm([1000, 500, 625])["lcm"] == 5000
    assert gcd_lcm([840, 384])["gcd"] == 24
    assert binomial_coefficient(45, 9)["value"] == 886163135
    assert convert_base_number("100101", 2, 10)["value"] == "37"
    assert convert_base_number(242345341, 10, 16)["value"] == "E71E57D"
    assert convert_base_number(190096544, 10, 5)["value"] == "342131042134"
    million = divisor_summary(1_000_000)
    assert million["count"] == 49
    assert million["sum"] == 2480437
    assert divisor_summary(24)["sum"] == 60
    with pytest.raises(ValueError):
        gcd_lcm([])
    with pytest.raises(ValueError):
        binomial_coefficient(9, 45)
    with pytest.raises(ValueError):
        convert_base_number("2", 2, 10)
    with pytest.raises(ValueError):
        convert_base_number(10, 10, 37)
    with pytest.raises(ValueError):
        divisor_summary(0)


def test_brain_tumor_validation_review_detects_narrative_contradictions():
    review = brain_tumor_validation_review()
    assert review["highest_reported"]["network"] == "ResNet101"
    assert review["highest_reported"]["accuracy_percent"] == pytest.approx(100 * 33 / 36)
    alex = review["networks"][0]["results"][-1]
    assert alex["total_images"] == 120
    assert alex["validation_images"] == 36
    assert alex["correct_predictions"] == 32
    assert alex["accuracy_percent"] == pytest.approx(100 * 32 / 36)
    google = review["networks"][1]["results"][-1]
    assert google["accuracy_percent"] == 75
    assert len(review["narrative_contradictions"]) == 2
    assert not review["model_evaluated"]
    assert not review["clinical_claim"]
