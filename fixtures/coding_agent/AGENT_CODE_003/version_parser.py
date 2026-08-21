def parse_version(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        raise ValueError("version must contain three components")
    return tuple(int(part) for part in parts)
