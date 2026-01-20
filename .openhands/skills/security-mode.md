---
name: security-mode
triggers:
  - security
  - secure
  - password
  - auth
  - authentication
  - token
  - secret
  - api key
---
When security is mentioned, you MUST:
- NEVER hardcode secrets, passwords, or API keys
- Always use environment variables for sensitive data
- Validate and sanitize all user inputs
- Use parameterized queries for database operations
- Check for SQL injection vulnerabilities
- Use secure random generators (secrets module, not random)
- Hash passwords properly (bcrypt, argon2, not MD5/SHA1)
- Use HTTPS for all external connections
- Implement proper error handling that doesn't leak information

Security checklist:
- [ ] No secrets in code
- [ ] Input validation
- [ ] Output encoding
- [ ] Error handling
- [ ] Authentication checks


