from typing import List


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> List[str]:
    """Splits text into overlapping chunks for context preservation."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and smaller than chunk_size")
    chunks = []
    start = 0
    text_length = len(text)
    while start < text_length:
        chunks.append(text[start:start + chunk_size])
        start += chunk_size - overlap
    return chunks
