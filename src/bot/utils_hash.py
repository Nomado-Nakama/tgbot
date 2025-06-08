import hashlib


def digest(txt: str) -> str:
    return hashlib.sha256(txt.encode()).hexdigest()
