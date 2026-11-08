import pytest

from agent_logging_system import LoggingAgent
from agent_logging_system.adapters import NeurogardenAdapter
from agent_logging_system.observation import LATENCY_GENERATION


class CaptureLogger(LoggingAgent):
    def __init__(self):
        super().__init__()
        self.observations = []

    def ingest(self, observation):
        self.observations.append(observation)
        super().ingest(observation)


def event():
    return {
        "ordinal": 1,
        "source": "android",
        "probabilities": [0.70, 0.20, 0.08, 0.02],
        "tau": 0.05,
        "zoe": {"accessible": 3, "complement": 1, "vocabularySize": 4, "normalized": 0.75},
        "tiny": {
            "probabilities": [22938, 6554, 2621, 655],
            "tau": 1638,
            "accessible": 3,
            "complement": 1,
            "vocabularySize": 4,
            "normalized": 0.75,
            "request": "800200000A0666599A199A0A3D028F",
            "response": "00030001000406669000",
        },
        "quantizationChanged": False,
    }


def test_verifies_three_planes_without_raw_payloads():
    logger = CaptureLogger()
    adapter = NeurogardenAdapter(logger)
    result = adapter.log_measurement(event(), latency_ms=7)
    assert result == {"status": "verified", "observations": 3, "ordinal": 1}
    assert [obs.agent_id for obs in logger.observations] == [
        "neurogarden.mobile", "neurogarden.tiny", "neurogarden.laptop",
    ]
    assert all(obs.latency_ms == 7 for obs in logger.observations)
    assert all(obs.input["equation_creator"] == NeurogardenAdapter.CREATOR for obs in logger.observations)
    serialized = repr([obs.input for obs in logger.observations])
    assert "0.70" not in serialized and "800200000A" not in serialized
    assert "request_sha256" in serialized
    assert adapter.get_state()["neurogarden"]["next_ordinal"] == 2


def test_duplicate_is_idempotent_and_gap_is_an_alarm():
    logger = CaptureLogger()
    adapter = NeurogardenAdapter(logger)
    adapter.log_measurement(event())
    assert adapter.log_measurement(event())["status"] == "duplicate"
    assert len(logger.observations) == 3
    later = event()
    later["ordinal"] = 3
    with pytest.raises(ValueError, match="revision gap"):
        adapter.log_measurement(later)
    assert adapter.get_state()["neurogarden"]["next_ordinal"] == 2
    assert logger.get_agent_state("neurogarden.review")["error_count"] == 1


def test_edited_apdu_is_rejected():
    logger = CaptureLogger()
    adapter = NeurogardenAdapter(logger)
    edited = event()
    edited["tiny"]["response"] = "00020002000406669000"
    with pytest.raises(ValueError, match="Tiny APDU witness"):
        adapter.log_measurement(edited)
    reviews = adapter.get_state()["neurogarden"]["pending_reviews"]
    assert reviews[0]["kind"] == "verification_failed"


def test_strict_equality_and_quantization_review():
    logger = CaptureLogger()
    adapter = NeurogardenAdapter(logger)
    equality = event()
    equality["tau"] = 0.20
    equality["zoe"] = {"accessible": 1, "complement": 3, "vocabularySize": 4, "normalized": 0.25}
    equality["tiny"].update({
        "tau": 6554, "accessible": 1, "complement": 3, "normalized": 0.25,
        "request": "800200000A199A599A199A0A3D028F",
        "response": "000100030004199A9000",
    })
    equality["quantizationChanged"] = True
    assert adapter.log_measurement(equality)["status"] == "verified"
    reviews = adapter.get_state()["neurogarden"]["pending_reviews"]
    assert reviews[0]["kind"] == "quantization_changed"


def test_payload_retention_is_explicit():
    logger = CaptureLogger()
    adapter = NeurogardenAdapter(logger, retain_payloads=True)
    adapter.log_measurement(event())
    assert logger.observations[0].input["request"].startswith("800200")
    assert logger.observations[0].input["probabilities"][0] == 0.70


def test_source_reading_is_cited_reference_not_clinical_authorization():
    logger = CaptureLogger()
    adapter = NeurogardenAdapter(logger)
    adapter.log_source_reading(
        "neurogarden.researcher",
        "Basic Applied Bioinformatics",
        "Chapter 9, section 9.1, page 59",
        "Global alignment compares comparable sequences end to end",
        latency_ms=12000,
        subject="bioinformatics",
        medical_context=True,
    )
    observation = logger.observations[0]
    assert observation.latency_kind == LATENCY_GENERATION
    assert observation.output["evidence_class"] == "reference"
    assert observation.output["authorized"] is False
    state = adapter.get_state()["neurogarden"]
    assert state["pending_reviews"][0]["kind"] == "clinical_reference"
    assert state["clinical_action_authorized"] is False


def test_missing_citation_is_rejected():
    adapter = NeurogardenAdapter(CaptureLogger())
    with pytest.raises(ValueError, match="citation"):
        adapter.log_source_reading("researcher", "book", "", "claim")


def test_human_review_is_recorded_without_action_authority():
    logger = CaptureLogger()
    adapter = NeurogardenAdapter(logger)
    adapter.log_review("helen", "imaging-resolution", "accepted")
    assert logger.observations[0].output == {
        "decision": "accepted", "clinical_action_authorized": False,
    }
    with pytest.raises(ValueError, match="review decision"):
        adapter.log_review("helen", "imaging-resolution", "perform-surgery")
