# Failure log

One entry per failing evaluation case. Keep it honest: interviewers value what you found and fixed.

| Case | Run / prompt version | What failed | Why (root cause) | What I changed | Result after |
|---|---|---|---|---|---|
| E13_narrative | real-v1 | | | | |
| E14_ocr_noise | real-v1 | | | | |
| R04_semantic_headers_hard | real-v1 | | | | |

## Template for each investigation
1. **Reproduce:** exact input and the model's raw output.
2. **Classify:** prompt problem, schema problem, rule problem, data problem, or model limit?
3. **Fix one thing at a time** and re-run the full suite (a fix must not raise the false-reject rate or break another case).
4. **Record** before/after scores with `--label`.

## real-v1 findings (gemini-3.5-flash-lite, 27 claims/agent cases + 40 risk files)

| Case | What failed | Root cause | What I changed | Result after |
|---|---|---|---|---|
| E04_naira_symbol | currency returned as "₦", expected "NGN" | Model followed the symbol in the document. My prompt never asked for an ISO code, and nothing normalised it. A rules problem, not a model-quality problem | Deterministic currency normalisation in `ClaimExtraction` (symbols and names -> ISO code), per the design rule "rules decide, the model proposes" | real-v2 and later: passes. Currency is now normalised to the ISO code by a rule. |
| A12_pidgin_hard | "wetin dey happen with my claim..." refused | The agent router is keyword-based, so the model is never involved. Not an LLM failure | Not fixed on purpose: adding this phrase would overfit the test. The real fix is LLM tool-calling in the router | open |

Measurement notes: real-v1 latency (p50 25 s) included client-side spacing and rate-limit retry waits, so it is not model latency.
Fixed so only the HTTP request is timed. Header-mapping calls were also missing from the ops numbers and are now counted.

## real-v2 findings (gemini-3.5-flash-lite, 37 claims/agent cases + 40 risk files)

| Case | What failed | Root cause | What I changed | Result after |
|---|---|---|---|---|
| E02_ddmmyyyy | "12/03/2026" read as 3 December (month-first), expected 12 March | The prompt never states a date convention, and the model is not consistent: this same case PASSED in real-v1 with the same model and temperature 0. A silent-corruption risk: wrong date, status "ok", no review | Rule: if the model reads an ambiguous numeric date month-first, apply the house day-first convention and record `date_ddmm_applied`. Also added rules for future dates and conflicting policy numbers, plus `--repeat N` to measure run-to-run variation | real-v4: the prompt now states DD/MM. Without the rule's help: 10 of 10 correct on 12/03/2026 (was 5 of 10), then 20 of 20 across four other ambiguous dates. Full suite 100% in 3 of 3 runs. Rule kept as a safety net; it logs date_ddmm_applied whenever it fires. |
| A12_pidgin_hard | Refused (unchanged from real-v1) | Keyword router; the model is not involved | Open. Real fix: LLM tool-calling in the router | open |

Notes: all 10 hold-out cases from batch 1 passed (Swahili, Pidgin, dotted layout, "1.2m", no-date-no-guess, injection variant).
That may mean the model is strong, or that my hold-outs are too easy: keep writing harder ones.
