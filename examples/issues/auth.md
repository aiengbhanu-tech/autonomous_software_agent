# Authentication returns 500 for long passwords

The authentication endpoint sometimes returns 500 when passwords exceed the
supported length. Diagnose and fix it.

Reproduction: POST /auth with a password longer than 72 UTF-8 bytes. The
length-limited verifier raises ValueError, which reaches the endpoint's generic
500 handler. A 19-character lock-emoji password also reproduces it.

Acceptance:
- Reject passwords longer than 72 UTF-8 bytes with 422 before calling the verifier.
- Exactly 72 bytes must still reach verification.
- Preserve the original password; do not truncate, normalize, or hash differently.
- Preserve successful credentials, invalid-credential 401s, and existing type checks.
- Source changes only. Run all regression tests and explain the patch.

This fixture models a length-limited backend. Its verifier is deliberately fake
and is not suitable for authentication in a deployed application.

