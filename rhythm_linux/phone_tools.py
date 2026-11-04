"""Which phone features can run on this machine, and which command-line tools they are missing.

Kept free of GTK so the check can be tested without a display.
"""
from . import iphone, phone_send


def missing_phone_tools() -> dict[str, list[str]]:
    """Phone features that cannot run here, each with the tools it is missing."""
    missing: dict[str, list[str]] = {}
    gone = iphone.tools_missing()
    if gone:
        missing["iPhone browsing"] = gone
    if not phone_send.available():
        missing["KDE Connect sending"] = ["kdeconnect-cli"]
    return missing


def missing_text(feature: str, tools: list[str]) -> str:
    """A sentence naming the feature and the tools it needs that are not installed."""
    return f"{feature} needs {', '.join(tools)}, which is not installed."


def startup_notice() -> str:
    """Sentences for every phone feature that cannot run, or an empty string if all can."""
    return " ".join(missing_text(feature, tools) for feature, tools in missing_phone_tools().items())
