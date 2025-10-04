"""
Dashboard package for tile management and examples.

This package provides dashboard tile examples and utilities for tile management,
separating data structures from API route handlers.
"""

from .examples import get_tile_examples, DASHBOARD_TILE_EXAMPLES

__all__ = [
    "get_tile_examples",
    "DASHBOARD_TILE_EXAMPLES",
]