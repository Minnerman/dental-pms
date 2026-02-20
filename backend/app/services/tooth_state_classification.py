from __future__ import annotations

from typing import Literal

ToothStateType = Literal[
    "implant",
    "bridge",
    "crown",
    "veneer",
    "inlay_onlay",
    "post",
    "root_canal",
    "filling",
    "extraction",
    "denture",
    "other",
]

_ORDERED_RULES: tuple[tuple[ToothStateType, tuple[str, ...]], ...] = (
    ("implant", ("implant", "fixture")),
    ("bridge", ("bridge", "pontic", "maryland")),
    ("crown", ("crown", "cap")),
    ("veneer", ("veneer",)),
    ("inlay_onlay", ("inlay", "onlay")),
    ("post", ("post", "core")),
    ("root_canal", ("root canal", "rct", "endodont")),
    ("filling", ("filling", "restoration", "composite", "amalgam", "gic", "glass ionomer")),
    ("extraction", ("extract", "extraction", "xla")),
    ("denture", ("denture", "partial", "full upper", "full lower")),
)


def classify_tooth_state_type(code_label: str | None) -> ToothStateType:
    label = str(code_label or "").strip().lower()
    if not label:
        return "other"

    for mapped_type, keywords in _ORDERED_RULES:
        if any(keyword in label for keyword in keywords):
            return mapped_type

    return "other"

