# Roosterly support ticket agent

## How to run

1. Python 3.10+ is required.
2. Copy `.env.example` to `.env`, then fill in the key and email from the assignment email.
3. On Windows: `py -m pip install -r requirements.txt`
4. Practice run: `py -m src.agent`
5. Reset and final run: `py -m src.agent --reset`
6. Run the labelled eval: `py eval/eval.py`
7. Run tests: `py -m unittest discover -s tests -v`

Environment variables are `HELPDESK_API_URL`, `HELPDESK_API_KEY`, `CANDIDATE_EMAIL`, and optional `CANDIDATE_NAME`.

## Decisions

- I use deterministic FAQ matching rather than an external model. The only permitted knowledge source is `candidate_pack/faq.md`; this keeps answers auditable and cheap.
- Dutch is the default. English and German replies use explicit language templates, while handoff notes are always English.
- Tickets not covered by FAQ text or covered by a mandatory human-only rule are handed to a human. Empty and obvious spam tickets are closed.

I used Copilot and Pylance to build and test the implementation. Customer ticket text is treated only as data and never as instructions.

## Reliability

The client keeps calls to at most five per second, retries 429 with `Retry-After`, retries 503 with exponential backoff, and never retries 409. An SQLite state file marks successful decisions locally, so reruns skip handled tickets. After a crash, it continues with open tickets and server 409 protection prevents duplicate replies. Logs contain ticket IDs, decisions and redacted excerpts; card/IBAN patterns are removed.

## Eval and fix

The eval fetches `GET /examples`, compares language, category, priority and action, and reports counts and accuracy before and after. The baseline is a fixed keyword classifier with no mandatory-rule escalation. The fix adds explicit human-only rules and FAQ-specific classification.

Live run against the 10 examples:

| Field | Baseline | After fix |
|---|---:|---:|
| Language | 80% (8/10) | 80% (8/10) |
| Category | 20% (2/10) | 60% (6/10) |
| Priority | 20% (2/10) | 60% (6/10) |
| Action | 50% (5/10) | 80% (8/10) |

For a typical run, API calls are 1 status/examples call set plus retrieval/action calls; a model is not used, so incremental model cost is EUR 0.00. Estimated total API cost per 100 tickets is EUR 0.00, excluding infrastructure.

## What I would improve

Next, I would evaluate retrieval and reply quality with human-reviewed Dutch paraphrases, plus a confidence threshold and a fallback handoff for ambiguous matches. I would clarify whether one-customer known outages should be P2 or P3 in a future brief.
