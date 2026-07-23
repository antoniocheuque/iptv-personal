#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "selection.json"
OUTPUT_DIR = ROOT / "playlists"
DEBUG_DIR = ROOT / "debug"
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
COUNTRY_FROM_ID_RE = re.compile(r'\.([a-z]{2})(?:@[^.]*)?$', re.I)


@dataclass
class Channel:
    name: str
    url: str
    attrs: Dict[str, str]

    @property
    def tvg_id(self) -> str:
        return self.attrs.get("tvg-id", "")

    @property
    def text(self) -> str:
        return " ".join(
            [self.name, self.tvg_id, self.attrs.get("tvg-language", "")]
        ).lower()


def norm(value: str) -> str:
    value = value.lower()
    for old, new in (
        ("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),
        ("ü","u"),("ñ","n")
    ):
        value = value.replace(old, new)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def download_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent":"iptv-personal/2.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_m3u(text: str) -> List[Channel]:
    channels: List[Channel] = []
    pending = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            attrs = dict(ATTR_RE.findall(line))
            name = line.rsplit(",", 1)[-1].strip()
            pending = (name, attrs)
        elif line.startswith("#"):
            continue
        elif pending:
            name, attrs = pending
            channels.append(Channel(name=name, url=line, attrs=attrs))
            pending = None
    return channels


def infer_country(channel: Channel) -> str:
    explicit = channel.attrs.get("tvg-country", "")
    if explicit:
        country = explicit.split(";")[0].split(",")[0].strip().upper()
        if len(country) == 2:
            return country
    match = COUNTRY_FROM_ID_RE.search(channel.tvg_id)
    return match.group(1).upper() if match else ""


def expand_allowed(category: str, cfg: dict) -> set[str]:
    groups = cfg["country_groups"]
    allowed: set[str] = set()
    for item in cfg["category_allowed_country_groups"].get(category, []):
        if item in groups:
            allowed.update(groups[item])
        elif len(item) == 2:
            allowed.add(item.upper())
    return allowed


def contains_pattern(text: str, patterns: Iterable[str]) -> bool:
    ntext = norm(text)
    return any(norm(pattern) in ntext for pattern in patterns)


def excluded(channel: Channel, cfg: dict) -> bool:
    if not channel.url.startswith(("http://", "https://")):
        return True
    return contains_pattern(channel.text, cfg["exclude_name_patterns"])


def preferred_id_match(channel: Channel, category: str, cfg: dict) -> bool:
    base_id = channel.tvg_id.split("@")[0]
    return base_id in cfg.get("preferred_exact_ids", {}).get(category, [])


def category_score(channel: Channel, category: str, cfg: dict) -> int:
    country = infer_country(channel)
    allowed = expand_allowed(category, cfg)
    if country not in allowed:
        return -10000

    text = norm(channel.text)
    patterns = cfg["preferred_name_patterns"].get(category, [])
    hits = sum(1 for pattern in patterns if norm(pattern) in text)

    if category == "Chile" and country != "CL":
        return -10000
    if category == "Latinoamérica" and country == "CL":
        return -10000
    if hits == 0 and category not in ("Chile", "Latinoamérica"):
        return -10000

    score = hits * 20

    if preferred_id_match(channel, category, cfg):
        score += 1000

    if country == "CL" and category == "Chile":
        score += 100

    if channel.attrs.get("tvg-logo"):
        score += 3
    if channel.tvg_id:
        score += 3

    language = norm(channel.attrs.get("tvg-language", ""))
    if "spanish" in language:
        score += 18
    elif "english" in language and category in {
        "Noticias", "Autos y motores", "Ciencia y espacio",
        "Música", "Finanzas y tecnología", "Documentales y cultura"
    }:
        score += 12

    name = norm(channel.name)
    if any(q in name for q in ("1080p", "720p", " hd ", "fhd")):
        score += 5
    if any(q in name for q in ("360p", "240p", "not 24 7")):
        score -= 8
    if channel.url.startswith("https://"):
        score += 2

    return score


def best_category(
    channel: Channel,
    cfg: dict,
    valid_categories: Iterable[str]
) -> Optional[Tuple[str, int]]:
    scored = [
        (category, category_score(channel, category, cfg))
        for category in valid_categories
    ]
    category, score = max(scored, key=lambda item: item[1])
    return (category, score) if score > -10000 else None


def dedupe_key(channel: Channel) -> str:
    base_id = channel.tvg_id.split("@")[0]
    return base_id or norm(re.sub(r"\([^)]*\)", "", channel.name))


def select(
    all_channels: List[Channel],
    version_cfg: dict,
    cfg: dict
) -> Tuple[List[Tuple[str, Channel]], List[str]]:
    categories = list(version_cfg["quotas"])
    buckets: Dict[str, List[Tuple[int, Channel]]] = {
        category: [] for category in categories
    }
    debug: List[str] = []

    for channel in all_channels:
        if excluded(channel, cfg):
            continue
        result = best_category(channel, cfg, categories)
        if result:
            category, score = result
            buckets[category].append((score, channel))

    chosen: List[Tuple[str, Channel]] = []
    seen_urls: set[str] = set()
    seen_keys: set[str] = set()

    for category in categories:
        exact_ids = cfg.get("preferred_exact_ids", {}).get(category, [])
        for wanted in exact_ids:
            candidates = [
                (score, channel)
                for score, channel in buckets[category]
                if channel.tvg_id.split("@")[0] == wanted
            ]
            candidates.sort(key=lambda item: (-item[0], norm(item[1].name)))
            if candidates:
                channel = candidates[0][1]
                key = dedupe_key(channel)
                if channel.url not in seen_urls and key not in seen_keys:
                    chosen.append((category, channel))
                    seen_urls.add(channel.url)
                    seen_keys.add(key)
                    debug.append(
                        f"PREFERRED | {category} | {channel.name} | "
                        f"{infer_country(channel)} | {channel.tvg_id}"
                    )

    counts = {
        category: sum(1 for current, _ in chosen if current == category)
        for category in categories
    }

    for category, quota in version_cfg["quotas"].items():
        candidates = sorted(
            buckets[category],
            key=lambda item: (-item[0], norm(item[1].name))
        )
        for score, channel in candidates:
            if counts[category] >= quota:
                break
            key = dedupe_key(channel)
            if channel.url in seen_urls or key in seen_keys:
                continue
            chosen.append((category, channel))
            seen_urls.add(channel.url)
            seen_keys.add(key)
            counts[category] += 1
            debug.append(
                f"SCORE={score} | {category} | {channel.name} | "
                f"{infer_country(channel)} | {channel.tvg_id}"
            )

    if len(chosen) < version_cfg["target"]:
        extras: List[Tuple[int, str, Channel]] = []
        for category, items in buckets.items():
            extras.extend(
                (score, category, channel)
                for score, channel in items
                if score > 0
            )
        extras.sort(key=lambda item: (-item[0], norm(item[2].name)))

        for score, category, channel in extras:
            key = dedupe_key(channel)
            if channel.url in seen_urls or key in seen_keys:
                continue
            chosen.append((category, channel))
            seen_urls.add(channel.url)
            seen_keys.add(key)
            debug.append(
                f"EXTRA SCORE={score} | {category} | {channel.name} | "
                f"{infer_country(channel)} | {channel.tvg_id}"
            )
            if len(chosen) >= version_cfg["target"]:
                break

    return chosen[:version_cfg["target"]], debug


def m3u_entry(category: str, channel: Channel) -> str:
    name = channel.name.replace('"', "'")
    return (
        f'#EXTINF:-1 tvg-id="{channel.tvg_id}" tvg-name="{name}" '
        f'tvg-logo="{channel.attrs.get("tvg-logo","")}" '
        f'group-title="{category}",{name}\n'
        f'{channel.url}'
    )


def write_playlist(
    name: str,
    selected: List[Tuple[str, Channel]],
    debug: List[str]
) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    DEBUG_DIR.mkdir(exist_ok=True)

    playlist_path = OUTPUT_DIR / f"iptv-{name}.m3u"
    lines = [
        '#EXTM3U x-tvg-url="https://iptv-org.github.io/epg/guides/cl/tvpassport.com.epg.xml"',
        f"# Generada automáticamente. Canales: {len(selected)}",
    ]
    lines.extend(m3u_entry(category, channel) for category, channel in selected)
    playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    debug_path = DEBUG_DIR / f"selection-{name}.txt"
    debug_path.write_text("\n".join(debug) + "\n", encoding="utf-8")

    print(f"{playlist_path}: {len(selected)} canales")
    for category in dict.fromkeys(category for category, _ in selected):
        count = sum(1 for current, _ in selected if current == category)
        print(f"  {category}: {count}")


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    print("Descargando lista pública de iptv-org...")
    channels = parse_m3u(download_text(cfg["source_playlist"]))
    print(f"Streams analizados: {len(channels)}")

    if not channels:
        print("No se encontraron streams.", file=sys.stderr)
        return 1

    for version_name, version_cfg in cfg["versions"].items():
        selected, debug = select(channels, version_cfg, cfg)
        write_playlist(version_name, selected, debug)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
