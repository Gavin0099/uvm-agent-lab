def normalize_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]
