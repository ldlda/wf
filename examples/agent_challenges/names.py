from __future__ import annotations


def short_model_name(model: str) -> str:
    """Return compact model labels for dense trial tables and session titles."""
    name = model.rsplit("/", 1)[-1]
    for suffix in ("-v4-flash-free", "-v2.5-free", "-3-ultra-free"):
        name = name.replace(suffix, "")
    return name


def short_challenge_name(challenge: str) -> str:
    """Return compact challenge labels without changing stored challenge ids."""
    return {
        "browser_click": "browser",
        "report_workflow": "report",
    }.get(challenge, challenge)
