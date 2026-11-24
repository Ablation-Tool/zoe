"""PromptArchitect - expert prompt-engineering assistant.

Treat prompts as structured artifacts (role, goal, input/output contracts,
constraints, self-checks). Analyze, refine, and diversify them into
production-ready forms.

    from prompt_architect import PromptArchitect

    architect = PromptArchitect()
    analysis = architect.analyze(prompt, context)
    refined = architect.refine(prompt, context)
    variants = architect.generate_variants(prompt, context, n=3)
"""

from .architect import PromptArchitect
from .corpus import BookCorpus, Retriever
from .models import (
    GroundingResult,
    PromptAnalysis,
    PromptComponents,
    PromptContext,
    PromptSpec,
    PromptVariant,
    Retrieved,
)

__all__ = [
    "PromptArchitect",
    "PromptContext",
    "PromptComponents",
    "PromptAnalysis",
    "PromptSpec",
    "PromptVariant",
    "Retrieved",
    "GroundingResult",
    "BookCorpus",
    "Retriever",
]

__version__ = "0.1.0"
