import asyncio
import unittest

from run_main import PopupOpenerPolicy


class PopupOpenerPolicyTests(unittest.TestCase):
    def test_sets_popup_compatible_policy_on_http_responses(self):
        messages = []

        async def app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/html"),
                    (b"cross-origin-opener-policy", b"unsafe-none"),
                ],
            })

        async def send(message):
            messages.append(message)

        asyncio.run(PopupOpenerPolicy(app)(
            {"type": "http"},
            None,
            send,
        ))

        response_headers = dict(messages[0]["headers"])
        self.assertEqual(
            response_headers[b"cross-origin-opener-policy"],
            b"same-origin-allow-popups",
        )
        self.assertEqual(response_headers[b"content-type"], b"text/html")


if __name__ == "__main__":
    unittest.main()
