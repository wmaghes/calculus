"""Phase 3: rule-based extraction of dates, people, organizations and events.

Deterministic on purpose: every extracted item is a character span in the
stored page text, so it can be verified exactly like a citation. No model is
involved, so there is nothing for a prompt-injection document to steer.
"""
