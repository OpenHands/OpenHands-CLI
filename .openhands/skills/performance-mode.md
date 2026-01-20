---
name: performance-mode
triggers:
  - performance
  - optimize
  - speed
  - fast
  - efficient
  - bottleneck
---
When optimizing for performance:
- Profile first, optimize second (measure before changing)
- Use list comprehensions instead of loops when possible
- Prefer generators for large datasets
- Use sets for membership testing (O(1) vs O(n))
- Cache expensive computations
- Use async/await for I/O-bound operations
- Consider using numba or cython for CPU-bound code
- Avoid premature optimization - make it work first, then make it fast

Performance tips:
- Use `__slots__` for classes with many instances
- Prefer `collections.deque` for queue operations
- Use `itertools` for efficient iteration
- Consider database indexing for queries


