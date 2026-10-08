# Troubleshooting

## `No ffmpeg exe could be found`

Re-run `INSTALL.bat` so `imageio-ffmpeg` is installed, or set:

```toml
[app]
ffmpeg_path = "C:\\path\\to\\ffmpeg.exe"
```

## Edge TTS empty / network error

Edge needs outbound HTTPS. Corporate proxies: fill `[proxy]`.
The pipeline will still render with a silent bed + captions if TTS fails.

## Pexels 401 / 429

Check the key. Add more keys to `pexels_api_keys` to rotate.
Or switch `media.provider` to `local`.

## Streamlit page is blank

Use `START.bat` / `scripts/launch.py --all`. Bind address is `0.0.0.0`.

## MoviePy / ImageMagick errors

FrameGenius renders with **FFmpeg directly**. ImageMagick is not required.

## Whisper is slow

Keep `subtitle.provider = "edge"` unless you need transcription of existing audio.

## Port already in use

```toml
[app]
port = 8080
webui_port = 8501
```

## Tests

```bash
.venv/bin/pytest -q
```
