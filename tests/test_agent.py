import unittest

from src.classifier import classify, detect_language, is_empty_or_spam, redact_payment_details


class ClassifierTests(unittest.TestCase):
    def test_password_question_is_nl_reply(self):
        decision = classify({"subject": "Wachtwoord vergeten", "body": "Hoe log ik weer in?"})
        self.assertEqual(decision.action, "reply")
        self.assertEqual(decision.language, "nl")
        self.assertIn("Wachtwoord vergeten", decision.draft_reply)

    def test_refund_is_handoff(self):
        decision = classify({"subject": "Terugbetaling", "body": "Ik wil mijn geld terug omdat wij gesloten waren."})
        self.assertEqual(decision.action, "handoff")
        self.assertEqual(decision.priority, "P2")

    def test_security_is_p1_handoff(self):
        decision = classify({"subject": "Security", "body": "Onze account is gehackt."})
        self.assertEqual(decision.action, "handoff")
        self.assertEqual(decision.priority, "P1")

    def test_spam_is_closed(self):
        decision = classify({"subject": "Best offer", "body": "Click here for cryptocurrency."})
        self.assertEqual(decision.action, "close")

    def test_payment_details_are_redacted(self):
        text = "IBAN NL91ABNA0417164300 card 4111 1111 1111 1111"
        redacted = redact_payment_details(text)
        self.assertNotIn("4111", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_language_detection(self):
        self.assertEqual(detect_language("Bitte ändern Sie die Rechnung"), "de")
        self.assertEqual(detect_language("Please change my employee"), "en")


if __name__ == "__main__":
    unittest.main()
