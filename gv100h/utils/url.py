import re


def normalize_openai_base_url(raw_url: str) -> str:
    """
    Normalizes OpenAI API base URL to ensure standard /v1 endpoint format without duplicates.
    Example:
      "http://localhost:8000" -> "http://localhost:8000/v1"
      "http://localhost:8000/v1/" -> "http://localhost:8000/v1"
      "http://localhost:8000/v1" -> "http://localhost:8000/v1"
    """
    if not raw_url:
        return "http://localhost:8000/v1"

    url = raw_url.strip().rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return url

