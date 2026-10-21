"""Shared labels and scope rules. The wording matches docs/labelling_guide.md."""
import re

THEMES = [
    "Delivery & Delay",
    "Food or Product Quality",
    "Wrong or Missing Items",
    "Refunds & Payments",
    "App Bugs & UX",
    "Customer Support",
    "Pricing, Fees & Offers",
    "Praise / No issue",
    "Other issue",
]
SENTIMENTS = ["Positive", "Neutral", "Negative"]
OWNERS = ["Operations", "Product", "Support", "Pricing", "None"]

MIN_CHARS = 5            # shorter 1-3 star reviews are too short to classify
MAX_COMPLAINT_SCORE = 3  # the LLM only sees reviews rated 1-3 stars


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9&/]+", "", str(text).lower())


_CANON = {_key(t): t for t in THEMES}


def normalise_theme(label: str) -> str:
    """Map near-miss labels (for example a missing comma) to the canonical theme name."""
    return _CANON.get(_key(label), str(label).strip())


def in_scope(score, content) -> bool:
    """True for reviews the LLM should classify: rated 1-3 stars and at least MIN_CHARS long."""
    return int(score) <= MAX_COMPLAINT_SCORE and len(str(content).strip()) >= MIN_CHARS
