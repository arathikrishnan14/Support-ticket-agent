import sqlite3
from pathlib import Path


class StateStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS handled (ticket_id TEXT PRIMARY KEY, handled_at TEXT)"
        )
        self.connection.commit()

    def is_handled(self, ticket_id: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM handled WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        return row is not None

    def mark_handled(self, ticket_id: str) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO handled(ticket_id, handled_at) VALUES (?, datetime('now'))",
            (ticket_id,),
        )
        self.connection.commit()

    def clear(self) -> None:
        self.connection.execute("DELETE FROM handled")
        self.connection.commit()
