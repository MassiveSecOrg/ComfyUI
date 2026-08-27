# Multi-User Authentication

## Overview

When ComfyUI is run in multi-user mode (`--multi-user` flag), authentication is required to prevent unauthorized access to user data and assets.

## Authentication Mechanism

Each user has a unique authentication token that is:
- Generated automatically when the user is created
- Stored securely on the server in `user_tokens.json`
- Required for all API requests in multi-user mode

## Getting Your Authentication Token

### For New Users

When creating a new user via `POST /users`, the response includes the authentication token:

```json
{
  "user_id": "username_uuid",
  "token": "your-authentication-token"
}
```

**Important**: Save this token securely. It will not be shown again.

### For Existing Users

If you have an existing user but don't have the token:
1. The token is stored in `<user_directory>/user_tokens.json` on the server
2. Server administrators can retrieve tokens from this file
3. Alternatively, a new user can be created

## Making Authenticated Requests

Include your user ID and token in every request using one of these methods:

### Method 1: Custom Headers (Recommended)

```
comfy-user: your-user-id
comfy-user-token: your-authentication-token
```

### Method 2: Authorization Header

```
Authorization: Bearer your-user-id:your-authentication-token
```

## Example Usage

```bash
# Create a new user
curl -X POST http://localhost:8188/users \
  -H "Content-Type: application/json" \
  -d '{"username": "alice"}'

# Response: {"user_id": "alice_abc123", "token": "xyz789..."}

# List user data (authenticated)
curl http://localhost:8188/userdata?dir=. \
  -H "comfy-user: alice_abc123" \
  -H "comfy-user-token: xyz789..."
```

## Security Notes

- Tokens are cryptographically random and cannot be guessed
- Tokens are validated using constant-time comparison to prevent timing attacks
- System users (prefixed with `__`) are blocked from HTTP access
- In single-user mode (default), no authentication is required

## Migration from Previous Versions

If you have an existing multi-user setup:
1. On first startup after this update, tokens will be automatically generated for all existing users
2. These tokens are saved to `user_tokens.json`
3. Clients must be updated to include authentication tokens in requests
4. The old `comfy-user` header alone is no longer sufficient for authentication
