# FrameGenius security

Author: kingscottishDEV N.A.S

## Encrypted database

- File: `data/framegenius.db.enc`
- Cipher: **AES-256-GCM**
- Key derivation: **HKDF-SHA256** from `FRAMEGENIUS_MASTER_KEY`
- Runtime SQLite is mode `600` and re-sealed on every flush
- Secret columns (API keys stored in the vault table) are encrypted again at rest
- `PRAGMA secure_delete = ON`

Lose the master key and the vault cannot be opened. Back it up offline.

## Identity

- Admin password hashed with **bcrypt** (scrypt fallback)
- HttpOnly session cookie, 12 hour TTL, SameSite=Lax
- CSRF token required on cookie-authenticated writes
- API keys (`fg_…`) stored as SHA-256 hashes only
- Lockout after 8 failed logins
- Login rate limit: 6 / minute / IP

## HTTP hardening

- CSP, `X-Frame-Options: DENY`, nosniff, Referrer-Policy, Permissions-Policy
- CORS allow-list (no `*`)
- Request size cap 12 MB
- API rate limit 180 / minute / IP
- Downloads resolved and confined to `outputs/`
- Swagger disabled unless `FRAMEGENIUS_EXPOSE_DOCS=1` or a valid session
- Logs never include query strings

## File permissions

Bootstrap sets `0600` on `.env`, `config.toml`, and the ciphertext.
`data/` is `0700`.

## First boot

`INSTALL.bat` / `scripts/bootstrap_env.py` writes `data/FIRST_LOGIN.txt` (mode 600).
The file is deleted after the first successful dashboard login.
Change the password in **Vault** immediately.

## Production checklist

1. Put the studio behind HTTPS and set `FRAMEGENIUS_COOKIE_SECURE=1` + `FRAMEGENIUS_HSTS=1`
2. Rotate `FRAMEGENIUS_ADMIN_PASSWORD`
3. Keep `FRAMEGENIUS_EXPOSE_DOCS=0`
4. Back up `data/framegenius.db.enc` **and** `FRAMEGENIUS_MASTER_KEY` separately
5. Do not commit `.env` or `config.toml`
