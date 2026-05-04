"""Live LLM integration tests.

These tests run the real CLI with a real LLM provider to validate
end-to-end behavior. They are disabled by default and require:

1. ``--run-live-llm`` pytest flag to enable
2. ``LLM_API_KEY`` and ``LLM_MODEL`` environment variables set

See tests/live_llm/README.md for details.
"""
