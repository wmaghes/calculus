"""Exception types.

Rule: exception messages are fixed strings or reason codes. They never carry
document text, query text, file names, or user-supplied values, because
exceptions end up in logs, HTTP errors and crash reports.
"""


class LexReviewError(Exception):
    """Base class. `code` is a stable machine-readable reason code."""

    code = "error"

    def __init__(self, code: str | None = None):
        if code is not None:
            self.code = code
        super().__init__(self.code)


class ConfigError(LexReviewError):
    code = "config_error"


class DataSafetyError(LexReviewError):
    """Refusal to touch data outside the approved synthetic test-data set."""

    code = "data_not_approved"


class AuthError(LexReviewError):
    code = "auth_failed"


class AccessDenied(LexReviewError):
    code = "access_denied"


class NotFound(LexReviewError):
    code = "not_found"


class CryptoError(LexReviewError):
    code = "crypto_error"


class KeyDestroyed(CryptoError):
    code = "key_destroyed"


class EgressBlocked(LexReviewError):
    code = "egress_blocked"


class AuditIntegrityError(LexReviewError):
    code = "audit_integrity"
