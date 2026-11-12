import os
import sys
from pathlib import Path

import streamlit
import uvicorn


class PopupOpenerPolicy:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_popup_policy(message):
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"cross-origin-opener-policy"
                ]
                headers.append((
                    b"cross-origin-opener-policy",
                    b"same-origin-allow-popups",
                ))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_popup_policy)


def resolve_path(path):
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base_path) / path


def main():
    app_path = resolve_path("app.py")
    port = int(os.environ.get("PORT", "8501"))
    host = os.environ.get("STREAMLIT_SERVER_ADDRESS", "127.0.0.1")
    app = PopupOpenerPolicy(streamlit.App(str(app_path)))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
