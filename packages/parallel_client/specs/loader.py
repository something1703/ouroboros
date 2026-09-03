"""Validates every `*.json` Task spec in this directory against
PARALLEL_INTEGRATION.md §3's rules at import time — raises `SpecValidationError` with
the offending rule the moment a bad spec is loaded, rather than failing opaquely at
the Parallel API when the spec is actually used.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from config.parallel import TASK_SPEC_MAX_CHARS

_SPECS_DIR = Path(__file__).parent

_FORBIDDEN_KEYWORDS = frozenset(
    {
        "contains",
        "format",
        "maxContains",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minContains",
        "minItems",
        "minLength",
        "minimum",
        "minProperties",
        "multipleOf",
        "pattern",
        "patternProperties",
        "propertyNames",
        "uniqueItems",
        "unevaluatedItems",
        "unevaluatedProperties",
    }
)
_MAX_NESTING = 5
_MAX_TOTAL_PROPERTIES = 100
_MAX_ENUM_VALUES = 500


class SpecValidationError(ValueError):
    """A `specs/*.json` file violates one of PARALLEL_INTEGRATION.md §3's rules."""


class _Counters:
    def __init__(self) -> None:
        self.properties = 0
        self.enum_values = 0


def _validate_node(node: Any, *, path: str, depth: int, counters: _Counters) -> None:
    if not isinstance(node, dict):
        raise SpecValidationError(f"{path}: schema node must be a JSON object, got {node!r}")

    for key in node:
        if key in _FORBIDDEN_KEYWORDS:
            raise SpecValidationError(f"{path}: forbidden keyword {key!r}")

    enum = node.get("enum")
    if isinstance(enum, list):
        counters.enum_values += len(enum)
        if counters.enum_values > _MAX_ENUM_VALUES:
            raise SpecValidationError(f"{path}: total enum values exceed {_MAX_ENUM_VALUES}")

    node_type = node.get("type")

    if node_type == "object":
        if depth > _MAX_NESTING:
            raise SpecValidationError(f"{path}: nesting exceeds {_MAX_NESTING}")
        if "anyOf" in node:
            raise SpecValidationError(f"{path}: root anyOf is forbidden")
        if node.get("additionalProperties") is not False:
            raise SpecValidationError(f"{path}: additionalProperties must be false")
        properties = node.get("properties")
        if not isinstance(properties, dict) or not properties:
            raise SpecValidationError(f"{path}: object node must have non-empty properties")
        required = node.get("required")
        if not isinstance(required, list) or set(required) != set(properties.keys()):
            raise SpecValidationError(f"{path}: every property must be listed in required")
        for prop_name, prop_schema in properties.items():
            counters.properties += 1
            if counters.properties > _MAX_TOTAL_PROPERTIES:
                raise SpecValidationError(
                    f"{path}: total properties exceed {_MAX_TOTAL_PROPERTIES}"
                )
            _validate_node(
                prop_schema, path=f"{path}.{prop_name}", depth=depth + 1, counters=counters
            )
        return

    if node_type == "array":
        items = node.get("items")
        if items is not None:
            _validate_node(items, path=f"{path}[]", depth=depth + 1, counters=counters)
        return

    # A leaf scalar (including an optional `["string","null"]`-style type list) —
    # already keyword/enum-checked above, nothing further to recurse into.


def validate_spec(spec_json: dict[str, Any], *, name: str) -> None:
    """Raises `SpecValidationError` on the first rule violation found."""
    serialized = json.dumps(spec_json)
    if len(serialized) > TASK_SPEC_MAX_CHARS:
        raise SpecValidationError(
            f"{name}: spec is {len(serialized)} chars, exceeds {TASK_SPEC_MAX_CHARS}"
        )
    _validate_node(spec_json, path=name, depth=1, counters=_Counters())


@cache
def load_specs() -> dict[str, dict[str, Any]]:
    """Loads and validates every `*.json` file in this directory. Import-time failure
    (via the module-level `SPECS` below) is deliberate — a broken spec must never reach
    a real Parallel Task call."""
    specs: dict[str, dict[str, Any]] = {}
    for path in sorted(_SPECS_DIR.glob("*.json")):
        with path.open() as f:
            spec_json = json.load(f)
        validate_spec(spec_json, name=path.stem)
        specs[path.stem] = spec_json
    return specs


SPECS: dict[str, dict[str, Any]] = load_specs()
