import os

# Unit tests never touch a real database or LLM.
os.environ.setdefault("OPENROUTER_API_KEY", "unit-test-key")
