import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from typing import Any, Dict, Iterable, Optional


class HelpdeskError(RuntimeError):
    pass


class HelpdeskClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        candidate_email: Optional[str] = None,
        candidate_name: Optional[str] = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("HELPDESK_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("HELPDESK_API_KEY", "")
        self.candidate_email = candidate_email or os.getenv("CANDIDATE_EMAIL", "")
        self.candidate_name = candidate_name or os.getenv("CANDIDATE_NAME", "")
        self.timeout = timeout
        self._calls: deque[float] = deque()

        if not self.base_url:
            raise HelpdeskError("HELPDESK_API_URL is required")
        if not self.api_key:
            raise HelpdeskError("HELPDESK_API_KEY is required")
        if not self.candidate_email:
            raise HelpdeskError("CANDIDATE_EMAIL is required")

    def _wait_for_rate_limit(self) -> None:
        now = time.monotonic()
        while self._calls and now - self._calls[0] >= 1.0:
            self._calls.popleft()
        if len(self._calls) >= 5:
            time.sleep(1.0 - (now - self._calls[0]))
            return self._wait_for_rate_limit()
        self._calls.append(time.monotonic())

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        retries: int = 6,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "X-Candidate-Email": self.candidate_email,
            "Accept": "application/json",
        }
        if self.candidate_name:
            headers["X-Candidate-Name"] = self.candidate_name
        if body is not None:
            headers["Content-Type"] = "application/json"

        for attempt in range(retries + 1):
            self._wait_for_rate_limit()
            data = json.dumps(body).encode("utf-8") if body is not None else None
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = response.read()
                    return json.loads(payload.decode("utf-8")) if payload else {}
            except urllib.error.HTTPError as exc:
                payload = exc.read().decode("utf-8", errors="replace")
                try:
                    error = json.loads(payload)
                except json.JSONDecodeError:
                    error = {"error": {"code": "http_error"}, "raw": payload}
                code = (
                    error.get("error", {}).get("code")
                    if isinstance(error.get("error"), dict)
                    else error.get("code")
                )
                if exc.code == 429 and attempt < retries:
                    retry_after = float(exc.headers.get("Retry-After", "1"))
                    time.sleep(max(retry_after, 0.25))
                    continue
                if exc.code == 503 and attempt < retries:
                    time.sleep(min(0.5 * (2 ** attempt), 8.0))
                    continue
                if exc.code == 409:
                    raise HelpdeskError("ticket_already_handled")
                raise HelpdeskError(f"http_{exc.code}:{code or 'unknown'}")
            except urllib.error.URLError as exc:
                if attempt < retries:
                    time.sleep(min(0.5 * (2 ** attempt), 8.0))
                    continue
                raise HelpdeskError(f"network_error:{exc.reason}")

    def status(self) -> Dict[str, Any]:
        return self.request("GET", "/status")

    def examples(self) -> Iterable[Dict[str, Any]]:
        data = self.request("GET", "/examples")
        return data.get("examples", data if isinstance(data, list) else [])

    def open_tickets(self) -> Iterable[Dict[str, Any]]:
        cursor: Optional[str] = None
        while True:
            query = {"limit": "10", "status": "open"}
            if cursor:
                query["cursor"] = cursor
            data = self.request("GET", "/tickets?" + urllib.parse.urlencode(query))
            yield from data.get("tickets", [])
            cursor = data.get("next_cursor")
            if not cursor:
                break

    def action(self, ticket_id: str, action: str, body: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", f"/tickets/{urllib.parse.quote(ticket_id, safe='')}/{action}", body)
