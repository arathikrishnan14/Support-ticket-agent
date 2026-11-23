import re
from dataclasses import dataclass
from typing import Optional


PAYMENT_RE = re.compile(
    r"(?<!\d)(?:\d[ -]?){12,19}(?!\d)|\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
    re.IGNORECASE,
)


MANDATORY_HANDOFF = {
    "refund": ("refund or disputed charge", ("terugbetaling", "teruggave", "geld terug", "refund", "gecrediteerd")),
    "cancel": ("cancellation or contract change", ("opzeg", "stopzetten", "contract wijzigen", "abonnement wijzigen")),
    "privacy": ("personal data request", ("avg", "gdpr", "persoonsgegevens", "gegevens verwijderen", "mijn data")),
    "security": ("possible security incident", ("gehackt", "hack", "datadiefstal", "beveiligingsincident", "ongeautoriseerde")),
    "legal": ("legal threat", ("advocaat", "dagvaarding", "rechter", "juridisch", "aangifte")),
    "leave": ("customer threatening to leave", ("weggaan", "opzeggen", "andere leverancier", "annuleren")),
}


FAQ = (
    ("F01", "Forgotten password", ("wachtwoord", "password", "login", "inloggen", "reset")),
    ("F02", "Adding a new employee", ("medewerker toevoegen", "nieuwe medewerker", "employee", "werknemer")),
    ("F03", "Swapping shifts", ("dienst ruil", "ruilen", "shift swap", "ruil aanbieden", "verzoeken")),
    ("F04", "Export to payroll", ("loon", "salaris", "payroll", "nmbrs", "loket", "afas", "uren export")),
    ("F05", "Plans and prices", ("prijs", "prijzen", "abonnement", "plan", "basis", "plus", "employee per month")),
    ("F06", "Invoices", ("factuur", "invoice", "btw", "rekening")),
    ("F07", "Multiple locations", ("vestiging", "locatie", "locations")),
    ("F08", "Languages", ("taal", "language", "sprache")),
    ("F09", "Where your data is stored", ("waar worden", "gegevens opgeslagen", "data stored", "eu", "frankfurt")),
    ("F10", "Ideas and feature requests", ("idee", "wens", "feature", "roadmap")),
    ("F11", "Outages and maintenance", ("storing", "uitval", "onderhoud", "status page", "offline")),
    ("F12", "Mobile app requirements", ("ios", "android", "mobiele app", "locatie toestemming", "location permission")),
)


@dataclass
class Decision:
    language: str
    category: str
    priority: str
    action: str
    reason: str
    draft_reply: Optional[str] = None
    handoff_note: Optional[str] = None
    confidence: float = 0.5


def redact_payment_details(text: str) -> str:
    return PAYMENT_RE.sub("[REDACTED]", text)


def detect_language(text: str) -> str:
    lowered = text.lower()
    de_markers = (" und ", " ich ", " die ", " ist ", " mit ", " für ", " bitte ", " ein ")
    en_markers = (" the ", " and ", " please ", " how ", " my ", " password ", " employee ")
    padded = f" {lowered} "
    if sum(marker in padded for marker in de_markers) >= 2:
        return "de"
    if sum(marker in padded for marker in en_markers) >= 2:
        return "en"
    return "nl"


def is_empty_or_spam(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True
    if len(lowered) < 3:
        return True
    spam = ("unsubscribe", "affordable leads", "casino", "viagra", "click here", "cryptocurrency")
    return any(marker in lowered for marker in spam)


def find_mandatory_handoff(text: str) -> Optional[str]:
    lowered = text.lower()
    for _, (reason, markers) in MANDATORY_HANDOFF.items():
        if any(marker in lowered for marker in markers):
            return reason
    return None


def find_faq(text: str) -> Optional[tuple[str, str]]:
    lowered = text.lower()
    matches = []
    for faq_id, title, markers in FAQ:
        score = sum(1 for marker in markers if marker in lowered)
        if score:
            matches.append((score, faq_id, title))
    if not matches:
        return None
    matches.sort(reverse=True)
    return matches[0][1], matches[0][2]


def classify(ticket: dict) -> Decision:
    subject = str(ticket.get("subject") or "")
    body = str(ticket.get("body") or "")
    text = f"{subject}\n{body}".strip()
    language = detect_language(text)

    if is_empty_or_spam(text):
        return Decision(language, "other", "P4", "close", "The ticket is empty or clearly spam.")

    handoff_reason = find_mandatory_handoff(text)
    if handoff_reason:
        return Decision(
            language,
            "billing" if handoff_reason in ("refund or disputed charge",) else "other",
            "P1" if handoff_reason in ("possible security incident", "legal threat") else "P2",
            "handoff",
            f"{handoff_reason.capitalize()} requires a human under the support rules.",
            handoff_note=f"{handoff_reason}. Ticket text: {redact_payment_details(text[:500])}",
            confidence=0.98,
        )

    faq_match = find_faq(text)
    if faq_match:
        faq_id, title = faq_match
        if faq_id == "F10":
            return Decision(
                language, "feature_request", "P4", "handoff",
                "Feature requests go on the public roadmap and individual delivery dates cannot be promised.",
                handoff_note="Feature request. Record the idea and share the roadmap process.",
                confidence=0.9,
            )

        category = "question"
        priority = "P4"
        if faq_id in ("F04", "F05", "F06", "F07"):
            category = "billing"
        if faq_id in ("F11", "F12"):
            category = "bug"
            priority = "P2" if faq_id == "F11" else "P3"

        if faq_id == "F01":
            reply = "Ga naar app.roosterly.nl/login, klik op \"Wachtwoord vergeten\" en voer je e-mailadres in. De resetlink is 60 minuten geldig; controleer na 10 minuten je spammap."
        elif faq_id == "F02":
            reply = "Ga naar Team → Medewerker toevoegen, voer naam, e-mailadres en contracturen in en klik op Uitnodigen. De medewerker ontvangt een installatie-e-mail."
        elif faq_id == "F03":
            reply = "Open de dienst in de app en tik op \"Ruil aanbieden\". Een collega met dezelfde rol kan de ruil accepteren. De manager keurt deze onder Rooster → Verzoeken goed."
        elif faq_id == "F04":
            reply = "Stel de koppeling in onder Instellingen → Koppelingen → Salaris. Roosterly exporteert goedgekeurde uren naar Nmbrs, Loket.nl, AFAS of als CSV."
        elif faq_id == "F05":
            reply = "Basis kost €4 per actieve medewerker per maand voor één locatie. Plus kost €6 per actieve medewerker per maand en bevat meerdere locaties, API-toegang en loonintegraties."
        elif faq_id == "F06":
            reply = "Facturen worden op de 1e van elke maand gemaild en zijn te downloaden onder Instellingen → Abonnement → Facturen."
        elif faq_id == "F07":
            reply = "Extra vestigingen zijn onderdeel van het Plus-plan. Voeg een vestiging toe via Instellingen → Vestigingen → Nieuwe vestiging."
        elif faq_id == "F08":
            reply = "De app ondersteunt Nederlands, Engels en Duits. Kies de gewenste taal bij Profiel → Taal."
        elif faq_id == "F09":
            reply = "Alle gegevens worden in de EU opgeslagen, in Frankfurt, Duitsland. De verwerkersovereenkomst staat onder Instellingen → Juridisch."
        elif faq_id == "F10":
            reply = "Bedankt voor het idee. Deel ideeën op roadmap.roosterly.nl, waar ze kunnen worden gestemd."
        elif faq_id == "F11":
            reply = "Bekijk de actuele status en geplande onderhoudsperioden op status.roosterly.nl."
        else:
            reply = "De app werkt op iOS 16 en later en Android 10 en later. Voor klokken via locatie is locatietoegang nodig."

        if language == "en":
            translated = {
                "F01": "Go to app.roosterly.nl/login, click \"Forgot password\", and enter your email address. The reset link is valid for 60 minutes; check your spam folder after 10 minutes.",
                "F02": "Go to Team -> Medewerker toevoegen (Add employee), enter the name, email address and contract hours, then click Uitnodigen (Invite).",
                "F03": "Open the shift in the app and tap \"Ruil aanbieden\" (Offer swap). A colleague with the same role can accept it; a manager approves requests under Rooster -> Verzoeken.",
                "F04": "Set up the integration under Instellingen -> Koppelingen -> Salaris (Settings -> Integrations -> Payroll). Approved hours can be exported to Nmbrs, Loket.nl, AFAS or CSV.",
                "F05": "Basis is EUR 4 per active employee per month for one location. Plus is EUR 6 per active employee per month and includes multiple locations, API access and payroll integrations.",
                "F06": "Invoices are emailed on the 1st of every month and are available under Instellingen -> Abonnement -> Facturen.",
                "F07": "Additional locations are part of Plus. Add one under Instellingen -> Vestigingen -> Nieuwe vestiging.",
                "F08": "The app is available in Dutch, English and German. Choose your language under Profile -> Language.",
                "F09": "Data is stored in the EU, in Frankfurt, Germany. The data processing agreement is available under Instellingen -> Juridisch.",
                "F11": "Check current outages and planned maintenance at status.roosterly.nl.",
                "F12": "The app requires iOS 16 or later and Android 10 or later. Clocking in with location requires location permission.",
            }
            reply = translated.get(faq_id, reply)
        elif language == "de":
            translated = {
                "F01": "Gehen Sie zu app.roosterly.nl/login, klicken Sie auf \"Wachtwoord vergeten\" und geben Sie Ihre E-Mail-Adresse ein. Der Reset-Link ist 60 Minuten gültig.",
                "F02": "Gehen Sie zu Team -> Medewerker toevoegen, geben Sie Name, E-Mail-Adresse und Vertragsstunden ein und klicken Sie auf Uitnodigen.",
                "F03": "Offnen Sie die Schicht in der App und tippen Sie auf \"Ruil aanbieden\". Kolleginnen und Kollegen mit derselben Rolle konnen den Tausch annehmen.",
                "F04": "Richten Sie die Integration unter Instellingen -> Koppelingen -> Salaris ein.",
                "F05": "Basis kostet 4 EUR pro aktivem Mitarbeiter und Monat. Plus kostet 6 EUR pro aktivem Mitarbeiter und Monat.",
                "F06": "Rechnungen werden am 1. jeden Monats per E-Mail versandt und konnen unter Instellingen -> Abonnement -> Facturen heruntergeladen werden.",
                "F07": "Standorte sind Teil des Plus-Plans.",
                "F08": "Die App ist auf Niederlandisch, Englisch und Deutsch verfugbar.",
                "F09": "Alle Daten werden in der EU, in Frankfurt, gespeichert.",
                "F11": "Aktuelle Storungen und Wartungen finden Sie unter status.roosterly.nl.",
                "F12": "Die App erfordert iOS 16 oder hoher und Android 10 oder hoher.",
            }
            reply = translated.get(faq_id, reply)

        return Decision(
            language, category, priority, "reply",
            f"Answered by {faq_id} ({title}). No mandatory human-only rule applies.",
            draft_reply=reply,
            confidence=0.9,
        )

    return Decision(
        language,
        "other",
        "P3",
        "handoff",
        "No FAQ entry reliably covers this ticket, so it requires human review.",
        handoff_note=f"Customer ticket not covered by the FAQ. Ticket text: {redact_payment_details(text[:500])}",
        confidence=0.7,
    )
