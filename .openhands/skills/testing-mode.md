---
name: testing-mode
triggers:
  - test
  - testing
  - unit test
  - pytest
  - coverage
---
When writing tests:
- Use pytest (not unittest)
- Follow AAA pattern: Arrange, Act, Assert
- Use descriptive test names: test_function_name_scenario_expected_result
- Use fixtures for setup/teardown
- Mock external dependencies
- Aim for high coverage but focus on meaningful tests
- Test edge cases and error conditions
- Use parametrize for testing multiple inputs

Example:
```python
import pytest
from unittest.mock import Mock, patch

def test_user_creation_with_valid_data_creates_user():
    # Arrange
    user_data = {"name": "John", "email": "john@example.com"}
    
    # Act
    user = create_user(user_data)
    
    # Assert
    assert user.name == "John"
    assert user.email == "john@example.com"
```


