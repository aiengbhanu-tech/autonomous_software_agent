"""Deliberately buggy WSGI endpoint. Demonstration only, not real authentication."""
import json

MAX_PASSWORD_BYTES = 72


class LengthLimitedVerifier:
    """Models a length-limited password backend; not a cryptographic verifier."""
    def verify(self, password):
        if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError("password exceeds supported byte length")
        return password == "demo-password"


def authenticate(payload, verifier=None):
    verifier = verifier or LengthLimitedVerifier()
    password = payload.get("password")
    if not isinstance(password, str):
        return 422, {"error": "password must be a string"}
    # BUG: overlong input reaches verifier and raises ValueError.
    valid = verifier.verify(password)
    return (200, {"authenticated": True}) if valid else (401, {"error": "invalid credentials"})


def application(environ, start_response):
    if environ.get("PATH_INFO") != "/auth" or environ.get("REQUEST_METHOD") != "POST":
        status, body = 404, {"error": "not found"}
    else:
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if not 0 <= length <= 8192:
                status, body = 413, {"error": "request too large"}
            else:
                payload = json.loads(environ["wsgi.input"].read(length))
                if not isinstance(payload, dict):
                    status, body = 422, {"error": "object required"}
                else:
                    status, body = authenticate(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            status, body = 400, {"error": "invalid JSON"}
        except Exception:
            status, body = 500, {"error": "internal server error"}
    labels = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found",
              413: "Content Too Large", 422: "Unprocessable Content", 500: "Internal Server Error"}
    encoded = json.dumps(body).encode("utf-8")
    start_response(f"{status} {labels[status]}", [("Content-Type", "application/json"), ("Content-Length", str(len(encoded)))])
    return [encoded]

