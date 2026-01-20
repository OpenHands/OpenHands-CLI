---
name: debug-helper
triggers:
  - debug
  - bug
  - error
  - fix
  - broken
  - not working
---
When debugging:
- First, reproduce the issue consistently
- Add logging to understand execution flow
- Use a debugger (pdb, ipdb) for step-by-step inspection
- Check error messages and stack traces carefully
- Verify assumptions with assertions
- Test edge cases that might cause issues
- Check for common issues:
  * Off-by-one errors
  * None/NoneType errors
  * Type mismatches
  * Race conditions in async code
  * Resource leaks (files, connections not closed)

Debugging checklist:
1. Can you reproduce it?
2. What's the error message?
3. What's the expected vs actual behavior?
4. What changed recently?
5. Are there any logs?


