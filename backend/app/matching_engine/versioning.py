"""Optimistic-lock helper for route_version (pure)."""

from __future__ import annotations


def next_route_version(current: int, expected: int | None) -> int | None:
    """
    Return new version if expected matches current; else None (conflict).
    """
    if expected is None:
        return current + 1
    if expected != current:
        return None
    return current + 1


def apply_version_guard(current: int, expected: int) -> bool:
    return current == expected
