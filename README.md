# FrameGenius

**by kingscottishDEV N.A.S**

A local AI film studio. Type a topic. It researches the web, writes a unique script, generates matching pictures, speaks the narration, and exports a ready-to-post MP4.

No login. No mock renders. Files land on your disk.

---

## Windows

1. Double-click **`APP.cmd`** for the desktop app window  
   or **`GO.cmd`** to use the browser
2. You land on **Generate** (no login)
3. Enter a topic → **Render film**
4. At 100% click **Download MP4** (also in `outputs\videos\`)
5. Optional: `tools\MAKE_SHORTCUT.cmd` puts FrameGenius on your Desktop

If pip says disk full: delete the `.venv` folder, empty Recycle Bin, run `INSTALL.bat` again.

Extract a new zip **over** `C:\Users\KingScottish\Desktop\FrameGenius`, keep `.venv`, then **Ctrl+F5** in the studio.

## What it does

| Agent | Job |
| --- | --- |
| Research | Scrapes the subject. Unique facts only. |
| Writer | Unique spoken script for the length you picked. Sticks to one subject. |
| Text | Hook, titles, caption colours for this film. |
| Voice | Edge TTS (or Windows SAPI). |
| Backgrounds | Unique pictures scaled to length — **30s → 6**, **5 min → ~25**. Crime gets police, gym gets gym. |
| Media | Coverr B-roll (no key) + Pexels/Pixabay if you paste a real key. |
| Caption | Timed captions in the film’s colours. |
| Editor / Publisher | Cut, mix, MP4 + post kit. |
| Upload | Drop a video. Bleeps swears only. Rest of the sound stays. |
| Factory | Trends, overnight batch, channel kit, Shorts. |

Lengths: **30s · 1m · 5m · 10m · 15m · 30m**

## Crown

The **Crown** tab is Crown AI. It talks through **`gemma4-pro:latest`**. Keep Ollama running. The 17 GB Gemma still writes the films.  
Ask for any image (any style) or click **Make a picture**. Files land in `outputs\images\`.  
Original work. No paid signup. Every film also ships captions + tags.

## Upload / bleeps

`INSTALL.cmd` tries `pip install vosk` (then `faster-whisper`) and **does not fail** if those wheels are missing.  
Python 3.14 often has no faster-whisper wheel — Vosk is the one that works. First bleep downloads ~40 MB to `models\vosk-small-en-us-0.15`.

Manual: `.venv\Scripts\pip install vosk`

## YouTube / TikTok

- **YouTube:** Settings → paste a free Google Cloud OAuth client id + secret → **Save** → **Connect YouTube**. Redirect must be `http://127.0.0.1:8080/api/v1/publish/youtube/callback` (and the localhost twin). Enable **YouTube Data API v3**. Default privacy is **unlisted**. Then Library / Generate result → **YouTube**.
- **TikTok:** no cookie bot. **TikTok** copies the caption pack and opens [TikTok Studio](https://www.tiktok.com/tiktokstudio/upload). Optional Upload-Post key if you already have one.

## Ollama

Writer default: `1stageze/gemma4-26b-uncensored-1m:latest`  
Crown: `gemma4-pro:latest` (it will never name the model — it's Crown)

Your pulled models show in the Generate / Settings dropdown, including:

- `1stageze/gemma4-26b-uncensored-1m:latest` (17 GB, uncensored — the brain)
- `gemma4-pro:latest`
- `qwen3.5-direct:latest` · `dzgg/Qwen3.5-Uncensored-HauhauCS-Aggressive:4b`
- `qwen3-8b-pro:latest`
- `qwen3.6-pro:latest` (23 GB — listed, never auto-picked if the 17 GB brain is there)
- `qwen-coder-fast:latest` · `qwen2.5-coder:1.5b-base`

Keep Ollama running on `127.0.0.1:11434`. Settings → paste OpenAI / Pexels later if you want.

## Docker / public URL

- `tools\DOCKER.bat`
- `tools\CLOUDFLARE.bat` (studio must already be running)
- [docs/DOCKER_AND_CLOUDFLARE.md](docs/DOCKER_AND_CLOUDFLARE.md)

## Login (off)

Auth code is still in the repo. Gate is off.  
To turn it on later: `FRAMEGENIUS_AUTH=1` in `.env`  
user `admin` / pass `FrameGenius!`

## License

MIT. © 2026 kingscottishDEV N.A.S
