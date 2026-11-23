import json
import os
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.classifier import classify, find_mandatory_handoff
from src.helpdesk_client import HelpdeskClient


def baseline(ticket: dict) -> Dict[str, object]:
    text = f"{ticket.get('subject') or ''} {ticket.get('body') or ''}".lower()
    faq_terms = {
        "F01": ("wachtwoord", "password"),
        "F02": ("medewerker", "employee"),
        "F03": ("ruil", "swap"),
        "F04": ("salaris", "payroll"),
        "F05": ("prijs", "abonnement"),
        "F06": ("factuur", "invoice"),
        "F07": ("vestiging", "locatie"),
        "F08": ("taal", "language"),
        "F09": ("gegevens", "data"),
        "F10": ("idee", "feature"),
        "F11": ("storing", "uitval"),
        "F12": ("ios", "android"),
    }
    for faq_id, terms in faq_terms.items():
        if any(term in text for term in terms):
            action = "handoff" if faq_id == "F10" else "reply"
            return {"language": "nl", "category": "question", "priority": "P4", "action": action}
    return {"language": "nl", "category": "other", "priority": "P3", "action": "handoff"}


def score(expected: dict, actual: dict) -> Dict[str, bool]:
    label = expected["label"]
    return {
        "language": actual["language"] == label["language"],
        "category": actual["category"] == label["category"],
        "priority": actual["priority"] == label["priority"],
        "action": actual["action"] == label["action"],
    }


def run() -> None:
    client = HelpdeskClient()
    examples = list(client.examples())
    totals = {"baseline": [0, 0, 0, 0], "fixed": [0, 0, 0, 0]}
    fields = ("language", "category", "priority", "action")

    for example in examples:
        baseline_decision = baseline(example)
        fixed_decision = classify(example)
        fixed = {
            "language": fixed_decision.language,
            "category": fixed_decision.category,
            "priority": fixed_decision.priority,
            "action": fixed_decision.action,
        }
        for index, field in enumerate(fields):
            totals["baseline"][index] += score(example, baseline_decision)[field]
            totals["fixed"][index] += score(example, fixed)[field]

    print(json.dumps({
        "count": len(examples),
        "baseline": dict(zip(fields, totals["baseline"])),
        "fixed": dict(zip(fields, totals["fixed"])),
        "baseline_accuracy": {f: round(totals["baseline"][i] / len(examples), 3) for i, f in enumerate(fields)},
        "fixed_accuracy": {f: round(totals["fixed"][i] / len(examples), 3) for i, f in enumerate(fields)},
    }, indent=2))


if __name__ == "__main__":
    run()
