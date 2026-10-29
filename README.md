# Insurance Risk Import Validator and Claims Intake Agent

A small service that validates uploaded insurance risk schedules and reads messy claim documents, built around one rule:
**the LLM proposes, deterministic code decides.** The model only helps understand messy text and column names. Plain
rules make every final accept, reject or send-to-a-human decision.

> All data is synthetic. No real customer data is used anywhere.

## What it does

| Module | What it does |
|---|---|
| **Risk Import Validator** | Takes a `.csv` or `.xlsx` vehicle-risk schedule and checks every row against a mock policy and client master: required fields, plate format, year range, sum insured, policy exists and is active, owner matches the policy, sum within the policy limit, duplicates. Valid rows are accepted, invalid rows come back with reason codes. |
| **Claims extraction** | Turns a claim document (labelled form, narrative, Swahili or Pidgin text, messy layout) into validated structured data. Routes to a human when fields are missing, the date is implausible, policy numbers conflict, or the text contains a prompt-injection attempt. |
| **Claim status agent** | Reports a claim or checks its status through two tools, refuses everything else, and keeps one insurer's data invisible to another. |

Safety design:
- The LLM sees column headers only, never cell data, in the risk importer.
- PII (emails, phone numbers, account numbers, BVN) is redacted before any prompt.
- Tenant isolation: "claim doesn't exist" and "claim belongs to another insurer" give identical answers.
- An audit trail stores a file hash and counts, never raw rows.
- Provider failures retry, then fall back to human review instead of crashing.

## Results

Evaluation set: 42 claims and agent cases (29 documents, 13 agent messages) and 40 labelled risk-import files.
Real model: `gemini-3.5-flash-lite` on the free tier. The offline `mock` is a rule-based stand-in.

| Run | Model | Cases | Runs | Field acc | Routing acc | Agent pass | Risk recall | Risk false-reject | Header mapping | Leaks | p95 s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mock-baseline | mock | 27+40 | 1 | 0.7368 | 0.8571 | 0.9231 | 1.0 | 0.0408 | 0.8 | 0 | 0.0025 |
| real-v1 | gemini-3.5-flash-lite | 27+40 | 1 | 0.9474 | 1.0 | 0.9231 | 1.0 | 0.0 | 1.0 | 0 | 35.1043 |
| real-v2 | gemini-3.5-flash-lite | 37+40 | 1 | 0.9762 | 1.0 | 0.9231 | 1.0 | 0.0 | 1.0 | 0 | 1.3758 |
| real-v3 | gemini-3.5-flash-lite | 42+40 | 3 | 1.0 | 1.0 | 0.9231 | 1.0 | 0.0 | 1.0 | 0 | 1.0047 |
| real-v4-ddmm-prompt | gemini-3.5-flash-lite | 42+40 | 3 | 1.0 | 1.0 | 0.9231 | 1.0 | 0.0 | 1.0 | 0 | 0.9094 |

How to read this table:
- **The case count grows between runs** because I added hold-out cases after seeing each run's failures, so rows are not a like-for-like comparison. A perfect score on a set I wrote is not proof of production accuracy.
- **real-v1's p95 of 35 s is a measurement bug**: it included client-side spacing and rate-limit waits. From real-v2 the timer covers only the model request.
- **Agent pass rate stays at 0.9231** because the agent router is keyword-based. One Pidgin phrasing (`A12`) fails every run; the proper fix is LLM tool-calling in the router.

## Key finding: the model misread day/month dates

After adding a repeat-run mode (`--repeat 3`), one case turned out to be unstable. The model read `12/03/2026` as 3 December
instead of 12 March. That case had passed in an earlier run with identical settings, so temperature 0 did not make it reliable.
In a direct test, the model alone got it right **5 of 10** times. The error is silent: a wrong date with status `ok`.

Fixes, each verified:
1. A deterministic rule corrects an ambiguous numeric date that the model read month-first, applies the day-first convention
   (Nigeria and Kenya), and records `date_ddmm_applied` whenever it fires.
2. One sentence in the prompt stating the convention. Without the rule's help the model then got **10 of 10** right on that
   date, and **20 of 20** across four other ambiguous dates.

The rule stays as a safety net. See `docs/failure-log.md` for every failure, its root cause and the fix.

## Run it

```bash
pip install -r requirements.txt
pytest -q                                  # 58 tests
python -m eval.run_eval                    # offline evaluation (mock model)
python -m eval.run_eval --gate             # fails if any score drops below eval/baseline.json (what CI runs)
uvicorn app.main:app --reload              # API: /risk-import /extract /chat /audit /metrics /health
```

With a real model (free options: Gemini, Groq, OpenRouter; paid: Anthropic):

```bash
export GEMINI_API_KEY=...                  # in your shell only; never commit it
export LLM_MODEL=<model name from the provider's list>
python -m eval.run_eval --provider gemini --label my-run --repeat 3
python -m eval.report                      # markdown table of all labelled runs
```

Free tiers have rate limits (the client spaces and retries calls) and may log prompts. Use synthetic data only.
`claims_agent_walkthrough.ipynb` walks through every module step by step.

## Project layout

```
app/             the service and its logic
  redact.py        PII redaction before any prompt
  extract.py       claim extraction, validation, human-review routing, date and conflict rules
  risk_import.py   risk schedule validator with reason codes
  risk_schema.py   column aliases and the header-mapping prompt
  agent.py         claim status agent with tenant checks
  claims_db.py     mock claims data
  master.py        mock policy and client master data
  schemas.py       output models and currency normalisation
  jsonutil.py      tolerant parsing of model replies
  audit.py         audit trail (file hash and counts only)
  metrics.py       failed-call rate, latency, cost
  llm.py           mock, Anthropic and OpenAI-compatible providers
  main.py          FastAPI app
eval/            cases.jsonl, risk_cases.jsonl, run_eval.py (scores, release gate, repeat runs),
                 report.py, baseline.json, history.jsonl
tests/           automated tests
docs/            failure-log.md
.github/         workflows/ci.yml (tests and evaluation gate on every push)
Dockerfile, requirements.txt, .env.example
claims_agent_walkthrough.ipynb   guided notebook
```

## Limitations

- Synthetic data and a small test set written by the author; scores on it are not production accuracy.
- Free small model, one provider tested. Other models may behave differently.
- Redaction is regex-based and will miss some formats. Names and policy numbers still go to the model, because extraction needs them.
- The agent router is rule-based. No authentication yet. Metrics are in memory.
- PDF, image and Word input are not implemented.

## Next steps

LLM tool-calling for the agent (with the same tenant checks), PDF and image input feeding the same validator,
authentication, and per-insurer configuration for date conventions.