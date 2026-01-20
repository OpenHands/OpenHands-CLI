---
name: documentation-mode
triggers:
  - document
  - documentation
  - docstring
  - comment
  - explain
---
When the user asks about documentation, comments, or explanations:
- Write EXTENSIVE docstrings with examples
- Include type information in docstrings
- Add inline comments for complex logic
- Explain the "why" not just the "what"
- Use Google-style docstrings
- Include usage examples in docstrings

Example format:
```python
def complex_function(param1: str, param2: int) -> dict[str, Any]:
    """Brief description.
    
    Longer explanation of what the function does and why it exists.
    
    Args:
        param1: Description of param1 with examples
        param2: Description of param2 with constraints
    
    Returns:
        Description of return value structure
    
    Raises:
        ValueError: When this happens
        TypeError: When that happens
    
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result)
        {'status': 'success'}
    """
```


