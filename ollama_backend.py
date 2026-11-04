import requests


DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


class OllamaError(RuntimeError):
    pass


def find_local_model(model_name, base_url=DEFAULT_OLLAMA_URL):
    try:
        response = requests.get(
            f"{base_url}/api/tags",
            timeout=(1, 2),
        )
    except requests.RequestException:
        return None, "Ollama is not running."

    if not response.ok:
        return None, f"Ollama returned HTTP {response.status_code}."

    try:
        models = response.json().get("models", [])
    except (ValueError, AttributeError) as error:
        raise OllamaError("Ollama returned an invalid installed-model list.") from error

    for model in models:
        if not isinstance(model, dict):
            continue
        installed_name = model.get("name") or model.get("model")
        if installed_name == model_name:
            return installed_name, None

    return None, f"Ollama model '{model_name}' is not installed."


def generate_json(model_name, messages, base_url=DEFAULT_OLLAMA_URL):
    try:
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": model_name,
                "messages": messages,
                "format": "json",
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.25,
                    "num_predict": 4096,
                },
            },
            timeout=(10, 300),
        )
    except requests.Timeout as error:
        raise OllamaError(
            "Ollama timed out while generating questions. Try again or check the "
            "computer's available memory."
        ) from error
    except requests.RequestException as error:
        raise OllamaError(
            f"Could not generate questions with Ollama: {error}"
        ) from error

    if not response.ok:
        try:
            detail = response.json().get("error", "")
        except (ValueError, AttributeError):
            detail = ""
        message = f"Ollama returned HTTP {response.status_code}."
        if detail:
            message += f" {detail}"
        raise OllamaError(message)

    try:
        content = response.json()["message"]["content"]
    except (ValueError, KeyError, TypeError) as error:
        raise OllamaError(
            "Ollama returned an invalid chat response."
        ) from error
    if not isinstance(content, str) or not content.strip():
        raise OllamaError("Ollama returned an empty response.")
    return content
