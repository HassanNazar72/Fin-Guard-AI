# Simple test statement — answer key

`simple_statement.csv` has 16 transactions over two months (January and February 2026). It uses round numbers so you can check every result by hand. Upload it with the **Upload CSV** button.

## Numbers you should see

| What | Expected | How to check by hand |
|---|---|---|
| Total income | £4,000.00 | 2 salaries × £2,000 |
| Total spend | £2,540.00 | Jan £1,005 + Feb £1,535 |
| Net cashflow | +£1,460.00 | 4,000 − 2,540 |
| Savings rate | 36.5% | 1,460 ÷ 4,000 |
| Detected anomalies | 3 | 1 duplicate + 1 outlier + 1 price rise |
| PII fields scrubbed | 3 | sort code + account number + card suffix |
| Injections blocked | 1 | the AMAZON row |

## Each planted feature

| Row | What it tests | Expected result |
|---|---|---|
| UBER EATS £20 at 19:00 and 20:00 on 15 Jan | Duplicate detection | Flagged as a possible duplicate, 1.0 hour apart |
| NETFLIX £10 → £15 | Subscription creep | +50.0%, an extra £60.00 a year |
| RENT £800 → £800 | Recurring payment, no change | Listed as recurring, not flagged |
| APPLE STORE £600 | Outlier detection | z-score 3.13. The threshold is £494.73, which is the £78.33 average plus 2.5 standard deviations; rent is excluded |
| TESCO (7 Jan, 15 Feb) | Not a subscription | Gap is 39 days, outside the 25–35 day window, so not recurring |
| COSTA £5 twice | Not a duplicate | Over 48 hours apart, so not flagged |
| `TRANSFER TO MUM 12-34-56 12345678` | PII scrubbing | Becomes `[SORT_CODE:tok_…] [ACCOUNT_NUMBER:tok_…]` |
| `PAYPAL CARD ENDING 1234` | PII scrubbing | Becomes `PAYPAL [CARD_SUFFIX:tok_…]` |
| `AMAZON *Ignore previous instructions…` | Prompt-injection defence | Becomes `AMAZON [INJECTION REMOVED]` |
| Dates in both `01/01/2026` and `2026-01-02` styles | Date cleaning | All shown as `YYYY-MM-DD` |
| Amounts like `£2,000.00` and `-£10.00` | Amount cleaning | Parsed as 2000.00 and -10.00 |

## Spend by category

| Category | Total |
|---|---|
| Housing | £1,600.00 |
| Shopping | £655.00 |
| Groceries | £110.00 |
| Transfers | £100.00 |
| Eating Out | £50.00 |
| Entertainment | £25.00 |
