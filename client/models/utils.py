def to_int(value: object) -> int:
    if isinstance(value, bool) or isinstance(value, float):
        return int(value)
    elif isinstance(value, int):
        return value
    elif isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0