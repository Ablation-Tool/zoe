"""Neural-signal observations alongside Dorothy's atlas geometry."""
from .neurogarden_dorothy import open_default_atlas_world
from .neurogarden_eeg import SOURCE, band_powers, higuchi_dimension, lyapunov_estimate, shannon_entropy


def neural_observation(samples, sample_rate):
    powers = band_powers(samples, sample_rate)
    return {
        "band_powers": powers,
        "lyapunov_estimate": lyapunov_estimate(samples),
        "higuchi_dimension": higuchi_dimension(samples),
        "entropy_bits": shannon_entropy(list(powers.values())),
        "source": SOURCE,
        "clinical_claim": False,
    }


def open_neural_world(samples, sample_rate, emblem=None):
    world = open_default_atlas_world(emblem=emblem)
    observation = neural_observation(samples, sample_rate)
    experiment = world.open(
        "neuroscience",
        "How do synthetic neural-signal bands and nonlinear measures vary?",
        SOURCE,
        "synthetic signals only; no patient diagnosis, disease classification, or clinical action",
    )
    world.measure(experiment.identifier, observation, "DFT bands, delay embedding, Higuchi, and entropy", "synthetic neural-signal teaching data")
    world.attachments["neural_observation"] = observation
    return world
