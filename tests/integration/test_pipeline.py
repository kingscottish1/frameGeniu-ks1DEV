from app.services.script import generate_script
from app.services.subtitle import build_subtitles


def test_script_to_captions(tmp_path):
    script = generate_script("deep work", provider="demo", duration=20)
    track = build_subtitles(script, duration=script.estimated_duration(), workdir=tmp_path)
    assert track.cues
    assert sum(cue.end - cue.start for cue in track.cues) > 5
