# Customization

## Templates

JSON files in `resource/templates/`. Add a new file and a matching writer in
`app/services/script.py` (`TEMPLATES` dict) if you want a unique voice.

Cover stills live in `resource/templates/covers/`.

## Fonts

Drop `.ttf` / `.otf` files into `resource/fonts/` and set:

```toml
[subtitle]
font = "Montserrat-Bold.ttf"
font_size = 64
font_color = "#FFFFFF"
highlight_color = "#F5C542"
position = "bottom"
```

## Music

Put royalty-free `mp3` / `wav` files in `resource/songs/`. The renderer picks one at random when BGM is on.

## Color grades

`cinematic` · `vivid` · `moody` · `none`

## Local B-roll

Drop videos or stills into `resource/media/`. Demo / local mode Ken-Burns the stills automatically.

## Watermark

```toml
[video]
watermark = true
watermark_text = "FrameGenius"
```
