import os
import sys
from pathlib import Path

import streamlit
import uvicorn


def resolve_path(path):
    base_path = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    return Path(base_path) / path


def main():
    app_path = resolve_path("app.py")
    port = int(os.environ.get("PORT", "8501"))
    host = os.environ.get("STREAMLIT_SERVER_ADDRESS", "127.0.0.1")
    app = streamlit.App(str(app_path))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
