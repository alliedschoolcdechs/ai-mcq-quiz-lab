import os
import unittest
from unittest.mock import patch

from run_main import main


class RunMainTests(unittest.TestCase):
    @patch("run_main.uvicorn.run")
    @patch("run_main.streamlit.App")
    def test_main_defaults_to_localhost(self, streamlit_app, uvicorn_run):
        app = object()
        streamlit_app.return_value = app
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PORT", "STREAMLIT_SERVER_ADDRESS"}
        }

        with patch.dict(os.environ, environment, clear=True):
            main()

        streamlit_app.assert_called_once()
        uvicorn_run.assert_called_once_with(app, host="127.0.0.1", port=8501)


if __name__ == "__main__":
    unittest.main()
