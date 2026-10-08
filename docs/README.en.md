# FrameGenius

Encrypted AI video studio by **kingscottishDEV N.A.S**.

## Install

Windows: `INSTALL.bat` then `RUN.bat`  
Unix: `./run.sh`

Dashboard: http://127.0.0.1:8080  
First login: `data/FIRST_LOGIN.txt` (removed after you sign in)

## Environment

Copy `.env.example` to `.env`. `INSTALL.bat` does this and generates:

- `FRAMEGENIUS_MASTER_KEY` — AES-256 vault key
- `FRAMEGENIUS_ADMIN_USER` / `FRAMEGENIUS_ADMIN_PASSWORD`

Never commit `.env`. Keep mode 600.

## Security

See [docs/SECURITY.md](docs/SECURITY.md). The database on disk is `data/framegenius.db.enc`.

## Archives

`dist/FrameGenius-kingscottishDEV-NAS.zip`  
`dist/FrameGenius-kingscottishDEV-NAS.tar.gz`

## License

MIT © 2026 kingscottishDEV N.A.S
