---
name: api-development
triggers:
  - api
  - endpoint
  - rest
  - http
  - route
---
When building APIs:
- Use FastAPI or Flask for REST APIs
- Always validate request data (use Pydantic models)
- Return proper HTTP status codes (200, 201, 400, 404, 500)
- Include error messages in consistent format
- Use versioning (e.g., /api/v1/)
- Document with OpenAPI/Swagger
- Implement rate limiting
- Add authentication/authorization
- Use proper HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Return JSON with consistent structure

Example response format:
```python
{
    "status": "success" | "error",
    "data": {...},
    "message": "Optional message",
    "errors": [...]  # Only on error
}
```


