# Labelling guide (version 1.1)

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
- Ignore vague opening words such as "worst app" or "horrible". If a review mentions several problems, choose the **first specific** problem it names.
- A complaint that names no area at all (just "bad", "worst") is `Other issue`. Praise with no detail is `Praise / No issue`.
- Naming support or customer care in a complaint ("horrible support") is `Customer Support`.
- A missing accessory or missing packaging (spoon, cutlery, carry bag, packaging) is `Wrong or Missing Items`. Damaged or spoiled items are `Food or Product Quality`.
- Judge theme and sentiment from the **text**. If the rating is low but the text only praises ("great"), label `Praise / No issue` and `Positive`.
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

## Version history
- 1.0: first guide.
- 1.1: added after reading the first dev scores. It resolves four ambiguities: vague opening words, naming support, missing accessories, and low rating with praising text. Dev labels that disagreed with these rules were revised; every test label is made under 1.1 without seeing any model output.
