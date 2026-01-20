---
name: python-style
triggers:
  - python
  - code
  - function
  - class
---
When writing Python code, you MUST follow these rules:
- Always use type hints on function parameters and return types
- Use f-strings instead of .format() or % formatting
- Prefer pathlib.Path over os.path
- Use dataclasses for simple data structures
- Add docstrings to all functions and classes
- Maximum line length: 88 characters (Black formatter standard)

Example of good code:
```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class User:
    name: str
    age: int

def process_file(file_path: Path) -> str:
    """Process a file and return its contents."""
    return file_path.read_text()
```


