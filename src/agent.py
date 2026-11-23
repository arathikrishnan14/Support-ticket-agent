import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .classifier import classify, redact_payment_details
from .helpdesk_client import HelpdeskClient, HelpdeskError
from .state import StateStore


def log_ticket(log_dir: Path, ticket: dict, decision, result: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticket_id": ticket["id"],
        "language": decision.language,
        "category": decision.category,
        "priority": decision.priority,
        "action": decision.action,
        "reason": decision.reason,
        "confidence": decision.confidence,
        "result": result,
        "customer_text": redact_payment_details(
            f"{ticket.get('subject') or ''} {ticket.get('body') or ''}"[:500]
        ),
    }
    with (log_dir / "agent.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def process_ticket(client: HelpdeskClient, store: StateStore, ticket: dict, log_dir: Path) -> None:
    ticket_id = ticket["id"]
    if store.is_handled(ticket_id):
        print(f"{ticket_id}: already handled locally; skipped")
        return

    decision = classify(ticket)
    body = {
        "language": decision.language,
        "category": decision.category,
        "priority": decision.priority,
        "reason": decision.reason,
        "confidence": decision.confidence,
    }
    if decision.action == "reply":
        body["draft_reply"] = decision.draft_reply
    elif decision.action == "handoff":
        body["handoff_note"] = decision.handoff_note

    try:
        client.action(ticket_id, decision.action, body)
    except HelpdeskError as exc:
        if str(exc) == "ticket_already_handled":
            store.mark_handled(ticket_id)
            log_ticket(log_dir, ticket, decision, "already_handled_on_server")
            print(f"{ticket_id}: server reports already handled; skipped")
            return
        log_ticket(log_dir, ticket, decision, f"failed:{exc}")
        raise

    store.mark_handled(ticket_id)
    log_ticket(log_dir, ticket, decision, "handled")
    print(f"{ticket_id}: {decision.action} ({decision.priority})")


def run(reset: bool = False) -> None:
    client = HelpdeskClient()
    store = StateStore(Path("state") / "handled.sqlite3")
    if reset:
        client.request("POST", "/practice/reset", {})
        store.clear()
    log_dir = Path("logs")
    for ticket in client.open_tickets():
        process_ticket(client, store, ticket, log_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Roosterly support ticket agent")
    parser.add_argument("--reset", action="store_true", help="Reset practice tickets before running")
    args = parser.parse_args()
    run(reset=args.reset)


if __name__ == "__main__":
    main()
