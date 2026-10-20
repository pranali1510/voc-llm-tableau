# Labelling guide (version 1)

Label every review yourself, from the review text and the star rating only. Do not use
any AI tool for the labels: they are the answer key the LLM will be scored against.

## true_theme: pick exactly one (the first problem the reviewer mentions)

| Label | Use it when the review is mainly about |
|---|---|
| `Delivery & Delay` | late or slow delivery, rider behaviour, tracking, wrong ETA, order not delivered |
| `Food or Product Quality` | stale, spoiled, cold, expired, damaged, poor taste or quality, hygiene |
| `Wrong or Missing Items` | an incorrect item, a missing item, short quantity |
| `Refunds & Payments` | refund not received, money deducted, payment failures, double charge, wallet or UPI issues |
| `App Bugs & UX` | crashes, login or OTP failure, location errors, cart or checkout errors, slow or hard-to-use app |
| `Customer Support` | chat bot, agents, no response, complaint not resolved |
| `Pricing, Fees & Offers` | delivery or platform fees, surge pricing, high prices, coupons or discounts not working |
| `Praise / No issue` | the review only praises the service or reports no problem |
| `Other issue` | a problem that fits none of the above, or a vague complaint ("worst app", "bad") |

Rules:
- If a review mentions several problems, choose the **first** one mentioned.
- A vague complaint with no detail is `Other issue`. Praise with no detail is `Praise / No issue`.
- If the text is empty, only emoji, or only symbols, label by rating: 4-5 stars `Praise / No issue`, otherwise `Other issue`.
- Money taken but order not delivered: `Refunds & Payments`. Order delivered late: `Delivery & Delay`.
- Do not change a label after you have seen any model output.

## true_sentiment: pick exactly one

| Label | Meaning |
|---|---|
| `Positive` | overall satisfied |
| `Neutral` | mixed or factual, neither clearly satisfied nor unsatisfied |
| `Negative` | overall dissatisfied |

Judge the whole review, not only the stars. A 5-star review that describes a serious problem is `Negative`.
