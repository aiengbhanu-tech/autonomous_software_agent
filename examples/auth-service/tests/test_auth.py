import io
import json
import unittest

from auth import application, authenticate


class SpyVerifier:
    def __init__(self):
        self.received = []

    def verify(self, value):
        self.received.append(value)
        return True


class AuthenticationTests(unittest.TestCase):
    def request(self, payload):
        body, response = json.dumps(payload).encode(), []
        environ = {"PATH_INFO": "/auth", "REQUEST_METHOD": "POST",
                   "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)}
        result = application(environ, lambda status, headers: response.append(status))
        return int(response[0].split()[0]), json.loads(b"".join(result))

    def test_known_valid_credentials(self):
        self.assertEqual(self.request({"password": "demo-password"})[0], 200)

    def test_invalid_credentials(self):
        self.assertEqual(self.request({"password": "wrong"})[0], 401)

    def test_oversized_ascii_returns_422_not_500(self):
        self.assertEqual(self.request({"password": "a" * 73})[0], 422)

    def test_utf8_byte_length(self):
        self.assertEqual(self.request({"password": "🔐" * 19})[0], 422)

    def test_exact_boundary_reaches_backend(self):
        spy = SpyVerifier()
        self.assertEqual(authenticate({"password": "é" * 36}, spy)[0], 200)
        self.assertEqual(spy.received, ["é" * 36])

    def test_oversize_does_not_reach_backend(self):
        spy = SpyVerifier()
        self.assertEqual(authenticate({"password": "é" * 37}, spy)[0], 422)
        self.assertEqual(spy.received, [])

    def test_password_not_truncated(self):
        spy = SpyVerifier()
        self.assertEqual(authenticate({"password": "x" * 72 + "suffix"}, spy)[0], 422)
        self.assertEqual(spy.received, [])

    def test_bad_types(self):
        for value in (None, 123, [], {}):
            with self.subTest(value=value):
                self.assertEqual(self.request({"password": value})[0], 422)

    def test_malformed_body(self):
        self.assertEqual(self.request([])[0], 422)

