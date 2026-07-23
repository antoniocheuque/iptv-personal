#!/usr/bin/env python3
"""
Genera listas IPTV personales desde la lista pública de iptv-org.

No almacena ni redistribuye video. Solo selecciona enlaces publicados en:
https://iptv-org.github.io/iptv/index.m3u
"""
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

ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


@dataclass
class Channel:
    name: str
    url: str
    attrs: Dict[str, str]
    source_group: str

    @property
    def text(self) -> str:
        values = [self.name, self.source_group]
        values.extend(self.attrs.values())
        return " ".join(values).lower()


def download_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "iptv-personal-generator/1.0"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_m3u(text: str) -> List[Channel]:
    channels: List[Channel] = []
    pending: Optional[Tuple[str, Dict[str, str]]] = None

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
            channels.append(
                Channel(
                    name=name,
                    url=line,
                    attrs=attrs,
                    source_group=attrs.get("group-title", "")
                )
            )
            pending = None

    return channels


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def is_excluded(channel: Channel, cfg: dict) -> bool:
    text = normalized(channel.text)
    if not channel.url.startswith(("http://", "https://")):
        return True
    return any(normalized(keyword) in text for keyword in cfg["exclude_keywords"])


def classify(channel: Channel, cfg: dict) -> Optional[str]:
    text = normalized(channel.text)
    country = channel.attrs.get("tvg-country", "").upper()
    language = channel.attrs.get("tvg-language", "")

    # Chile tiene prioridad para evitar que sus canales terminen en otras categorías.
    if country == "CL" or any(normalized(k) in text for k in cfg["priority_keywords"]["Chile"]):
        return "Chile"

    scores: Dict[str, int] = {}
    for category, keywords in cfg["priority_keywords"].items():
        if category == "Chile":
            continue
        score = sum(3 for keyword in keywords if normalized(keyword) in text)
        if score:
            scores[category] = score

    latin_countries = {"AR", "MX", "CO", "PE", "UY", "PY", "BO", "EC", "VE", "CR", "PA", "DO", "GT", "HN", "SV", "NI"}
    if country in latin_countries:
        scores["Latinoamérica"] = scores.get("Latinoamérica", 0) + 2

    if not scores:
        return None

    return max(scores.items(), key=lambda item: item[1])[0]


def quality_score(channel: Channel, category: str, cfg: dict) -> int:
    text = normalized(channel.text)
    score = 0

    country = channel.attrs.get("tvg-country", "").upper()
    language = channel.attrs.get("tvg-language", "")

    if country in cfg["preferred_countries"]:
        score += 8
    if language in cfg["preferred_languages"]:
        score += 8

    # Preferencia por español en categorías generales.
    if language == "Spanish":
        score += 6
    elif language == "English" and category in {
        "Autos y motores", "Ciencia y espacio", "Música",
        "Finanzas y tecnología", "Noticias"
    }:
        score += 5

    if any(token in text for token in (" hd ", " 1080", "720p", " fhd ")):
        score += 3
    if channel.attrs.get("tvg-logo"):
        score += 1
    if channel.attrs.get("tvg-id"):
        score += 1

    for keyword in cfg["priority_keywords"].get(category, []):
        if normalized(keyword) in text:
            score += 4

    # Se penalizan duplicados regionales y señales de prueba.
    if any(token in text for token in ("test", "backup", "mirror", "duplicate")):
        score -= 10

    return score


def dedupe(channels: Iterable[Channel]) -> List[Channel]:
    seen_urls = set()
    seen_names = set()
    result = []

    for channel in channels:
        key_name = normalized(channel.name)
        if channel.url in seen_urls or key_name in seen_names:
            continue
        seen_urls.add(channel.url)
        seen_names.add(key_name)
        result.append(channel)

    return result


def select_version(all_channels: List[Channel], version_cfg: dict, cfg: dict) -> List[Tuple[str, Channel]]:
    buckets: Dict[str, List[Channel]] = {category: [] for category in version_cfg["quotas"]}

    for channel in all_channels:
        if is_excluded(channel, cfg):
            continue
        category = classify(channel, cfg)
        if category in buckets:
            buckets[category].append(channel)

    chosen: List[Tuple[str, Channel]] = []
    global_urls = set()
    global_names = set()

    for category, quota in version_cfg["quotas"].items():
        candidates = sorted(
            dedupe(buckets[category]),
            key=lambda ch: (-quality_score(ch, category, cfg), normalized(ch.name))
        )

        count = 0
        for channel in candidates:
            name_key = normalized(channel.name)
            if channel.url in global_urls or name_key in global_names:
                continue
            chosen.append((category, channel))
            global_urls.add(channel.url)
            global_names.add(name_key)
            count += 1
            if count >= quota:
                break

    # Completa hasta el objetivo con los mejores canales restantes.
    if len(chosen) < version_cfg["target"]:
        extras: List[Tuple[int, str, Channel]] = []
        for category, candidates in buckets.items():
            for channel in dedupe(candidates):
                if channel.url in global_urls or normalized(channel.name) in global_names:
                    continue
                extras.append((quality_score(channel, category, cfg), category, channel))

        extras.sort(key=lambda item: (-item[0], normalized(item[2].name)))
        for _, category, channel in extras:
            chosen.append((category, channel))
            global_urls.add(channel.url)
            global_names.add(normalized(channel.name))
            if len(chosen) >= version_cfg["target"]:
                break

    return chosen[:version_cfg["target"]]


def m3u_line(category: str, channel: Channel) -> str:
    tvg_id = channel.attrs.get("tvg-id", "")
    tvg_logo = channel.attrs.get("tvg-logo", "")
    safe_name = channel.name.replace('"', "'")
    return (
        f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{safe_name}" '
        f'tvg-logo="{tvg_logo}" group-title="{category}",{safe_name}\n'
        f'{channel.url}'
    )


def write_playlist(name: str, selected: List[Tuple[str, Channel]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"iptv-{name}.m3u"
    lines = [
        '#EXTM3U x-tvg-url="https://iptv-org.github.io/epg/guides/cl/tvpassport.com.epg.xml"',
        f"# Generada automáticamente. Canales: {len(selected)}",
    ]
    lines.extend(m3u_line(category, channel) for category, channel in selected)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{path.relative_to(ROOT)}: {len(selected)} canales")


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    print("Descargando lista pública de iptv-org...")
    text = download_text(cfg["source_playlist"])
    channels = parse_m3u(text)
    print(f"Streams encontrados: {len(channels)}")

    if not channels:
        print("No fue posible analizar canales.", file=sys.stderr)
        return 1

    for version_name, version_cfg in cfg["versions"].items():
        selected = select_version(channels, version_cfg, cfg)
        write_playlist(version_name, selected)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
