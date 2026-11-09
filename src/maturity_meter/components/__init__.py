"""Components for evaluating software maturity,
computing each components individually (in subpackages)
and combined.
"""

from .combine import combine

__all__ = [
    "combine"
]