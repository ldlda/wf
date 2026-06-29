from __future__ import annotations


def short_model_name(model: str) -> str:
    """Return compact model labels for dense trial tables and session titles."""
    name = model.rsplit("/", 1)[-1]
    return {
        "deepseek-v4-flash-free": "deepseek",
        "mimo-v2.5-free": "mimo",
        "nemotron-3-ultra-free": "nemotron",
        "north-mini-code-free": "north",
    }.get(name, name)


def short_challenge_name(challenge: str) -> str:
    """Return compact challenge labels without changing stored challenge ids."""
    return {
        "browser_click": "browser",
        "report_workflow": "report",
    }.get(challenge, challenge)
