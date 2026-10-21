"""A simple keyword baseline for the complaint themes, to compare the LLM against.

Weighted whole-word rules (strong keywords count 2, weak keywords count 1). The theme
with the highest score wins; ties go to the theme whose strong keyword appears first;
no match gives 'Other issue'. Sentiment comes from the star rating only.
These rules are fixed BEFORE looking at the test labels. Do not tune them on the test set.
"""
import re

RULES = {
    "Delivery & Delay": (
        [r"late", r"delay\w*", r"rider", r"delivery partner", r"eta", r"tracking", r"not delivered",
         r"never delivered", r"never arrived", r"delivery time", r"hours?"],
        [r"waiting", r"wait", r"slow", r"delivery"]),
    "Food or Product Quality": (
        [r"stale", r"spoil\w*", r"rotten", r"expired?", r"expiry", r"quality", r"taste", r"cold", r"raw",
         r"smell\w*", r"damaged?", r"hygiene", r"fresh", r"burnt", r"bad food"],
        [r"food", r"product", r"packaging"]),
    "Wrong or Missing Items": (
        [r"missing", r"wrong", r"incorrect", r"not received", r"less quantity", r"short", r"different item"],
        [r"items?"]),
    "Refunds & Payments": (
        [r"refund\w*", r"payments?", r"paid", r"deducted?", r"double charge\w*", r"wallet", r"upi",
         r"cashback", r"transaction", r"money"],
        [r"charged?", r"card", r"bank"]),
    "App Bugs & UX": (
        [r"app", r"crash\w*", r"log ?in", r"otp", r"bugs?", r"error\w*", r"glitch\w*", r"location",
         r"loading", r"updates?", r"not opening", r"not working"],
        [r"open", r"interface", r"screen", r"cart", r"checkout"]),
    "Customer Support": (
        [r"support", r"customer care", r"chat ?bot", r"agent", r"executive", r"complain\w*", r"helpline",
         r"no response", r"resolv\w*", r"tickets?", r"customer service"],
        [r"response", r"service", r"call", r"contact"]),
    "Pricing, Fees & Offers": (
        [r"price\w*", r"pricing", r"fees?", r"expensive", r"costly", r"surge", r"mrp", r"coupons?",
         r"discounts?", r"offers?", r"delivery charges?", r"platform fee", r"handling"],
        [r"charges?", r"cost", r"rates?"]),
}
PATTERNS = {
    theme: (re.compile(r"\b(?:" + "|".join(strong) + r")\b", re.I),
            re.compile(r"\b(?:" + "|".join(weak) + r")\b", re.I))
    for theme, (strong, weak) in RULES.items()
}


def predict_theme(text: str) -> str:
    scores, first = {}, {}
    for theme, (strong, weak) in PATTERNS.items():
        s_matches = list(strong.finditer(text))
        scores[theme] = 2 * len(s_matches) + len(weak.findall(text))
        first[theme] = s_matches[0].start() if s_matches else 10**9
    best = max(scores.values())
    if best == 0:
        return "Other issue"
    tied = [t for t, v in scores.items() if v == best]
    return min(tied, key=lambda t: first[t])


def predict_sentiment(score: int) -> str:
    return "Negative" if score <= 2 else "Neutral"
