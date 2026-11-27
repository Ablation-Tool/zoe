"""AvailGate's CLI-independent API. Imports do not load search providers."""

__version__ = "0.2.0"


def search(query, **options):
    from .search import search as run
    return run(query, **options)


def read(url, **options):
    from .reader import read as run
    return run(url, **options)
