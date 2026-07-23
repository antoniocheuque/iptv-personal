from pathlib import Path
import importlib.util

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_playlists.py"
spec = importlib.util.spec_from_file_location("generator", SCRIPT)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

def test_norm():
    assert generator.norm("Chilevisión HD") == "chilevision hd"

def test_country_from_id():
    ch = generator.Channel(
        name="TVN",
        url="https://example.com/stream.m3u8",
        attrs={"tvg-id": "TVN.cl"}
    )
    assert generator.infer_country(ch) == "CL"

def test_dedupe_key():
    ch = generator.Channel(
        name="TVN (1080p)",
        url="https://example.com/stream.m3u8",
        attrs={"tvg-id": ""}
    )
    assert generator.dedupe_key(ch) == "tvn"
