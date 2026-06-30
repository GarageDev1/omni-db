# omni-db SAE Deployment

This directory contains deployment files owned by the omni-db application.

Casdoor is a separate service. omni-db should integrate with Casdoor only through OAuth/OIDC and should not read from or share the Casdoor database.

## Current Public Endpoints

- omni-db: `https://omnidb.suanlijie.com`
- Casdoor SSO endpoint: `https://casdoor.suanlijie.com`
- omni-db callback: `https://omnidb.suanlijie.com/auth/callback`

## Required Environment

The deployed omni-db SAE app needs the normal application settings plus:

```env
CASDOOR_ENDPOINT=https://casdoor.suanlijie.com
CASDOOR_CLIENT_ID=<casdoor application client id>
CASDOOR_CLIENT_SECRET=<casdoor application client secret>
CASDOOR_REDIRECT_URI=https://omnidb.suanlijie.com/auth/callback
CASDOOR_SCOPE=openid profile email
CASDOOR_ORG_NAME=garage
CASDOOR_APP_NAME=omni-db
CASDOOR_ADMIN_ROLES=admin,omni-admin
CASDOOR_EDITOR_ROLES=editor,omni-editor
```

Do not add Casdoor database credentials to omni-db.

## Runtime Boundary

omni-db owns:

- `Dockerfile.sae`
- `deploy/sae/nginx.conf`
- `deploy/sae/start.py`
- the `omnidb` application database
- the frontend callback route `/auth/callback`
- the backend route `/api/v1/auth/casdoor/callback`

Casdoor owns:

- its own SAE app
- its own RDS instance and `casdoor` database
- external identity providers such as Feishu/Lark
- the OAuth application definition for `omni-db`

## Verify

```bash
curl -fsS https://omnidb.suanlijie.com/health
curl -fsS https://omnidb.suanlijie.com/api/v1/auth/casdoor/config | jq .
```

The config endpoint should report:

```text
enabled=true
endpoint=https://casdoor.suanlijie.com
redirect_uri=https://omnidb.suanlijie.com/auth/callback
```

