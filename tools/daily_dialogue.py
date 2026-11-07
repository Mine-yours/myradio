#!/usr/bin/env python3
"""Generate a sourced two-speaker episode. Requires OPENAI_API_KEY and ffmpeg."""
import datetime as dt
import json
import os
import pathlib
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "radio_config.json").read_text())
API_KEY = os.environ.get("OPENAI_API_KEY", "")

def api(path, payload, binary=False):
    req = urllib.request.Request("https://api.openai.com/v1/" + path,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as response:
        return response.read() if binary else json.load(response)

def collect():
    entries = []
    for url in CONFIG["rss_feeds"]:
        req = urllib.request.Request(url, headers={"User-Agent": "PersonalRadio/1.0"})
        with urllib.request.urlopen(req, timeout=25) as response:
            xml = ET.fromstring(response.read(2_000_000))
        for item in xml.findall(".//item")[:10]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            description = item.findtext("description", "").strip()
            if title and link.startswith("https://"):
                entries.append({"title": title, "url": link, "description": description[:800]})
    return entries[:max(1, int(CONFIG["max_items"]))]

def make_script(items):
    instructions = """日本語の2人対話ラジオ台本をJSONだけで返す。
形式: {"title":"...", "news":[{"label":"...", "url":"...", "points":["..."], "lines":[{"speaker":"host|guest","say":"...","show":"..."}]}]}
ニュースは入力にある記事のみ使用し、URLは入力のものをそのまま使用。記事に書かれていない事実は断定しない。
各ニュースでhostとguestが交互に話す。全体で約60〜120秒。各発話は短く。"""
    response = api("chat/completions", {"model": CONFIG["model"], "response_format":{"type":"json_object"},
        "messages":[{"role":"system","content":instructions},
                    {"role":"user","content":json.dumps({"topics":CONFIG["topics"],"items":items},ensure_ascii=False)}]})
    return json.loads(response["choices"][0]["message"]["content"])

def duration(path):
    result = subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(path)],text=True)
    return float(result.strip())

def main():
    if not CONFIG.get("enabled"):
        print("Radio disabled: set enabled=true after configuring feeds.")
        return
    if not CONFIG["rss_feeds"]:
        print("No RSS feeds configured; no episode generated.")
        return
    if not API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required")
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    dest = ROOT / "episodes" / (today + "-ja.json")
    if dest.exists():
        print("Episode already exists:", dest)
        return
    items = collect()
    if not items:
        raise RuntimeError("No sourced RSS items found; refusing to fabricate news")
    script = make_script(items)
    allowed = {i["url"] for i in items}
    news = script.get("news", [])
    if not news or any(n.get("url") not in allowed for n in news):
        raise ValueError("Generated script contains unknown or missing sources")
    lines = []
    segments = []
    audio_dir = ROOT / "audio"
    audio_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        temp = pathlib.Path(temp)
        clips = []
        current = 0.0
        for index, story in enumerate(news):
            start = current
            for line in story["lines"]:
                speaker = line["speaker"]
                if speaker not in ("host","guest") or not line.get("say") or not line.get("show"):
                    raise ValueError("Invalid dialogue line")
                data = api("audio/speech", {"model":CONFIG["tts_model"],"voice":CONFIG["voices"][speaker],
                    "input":line["say"],"response_format":"mp3"}, binary=True)
                clip = temp / ("%04d.mp3" % len(clips))
                clip.write_bytes(data)
                end = current + duration(clip)
                lines.append({"start":round(current,3),"end":round(end,3),"show":line["show"],
                              "speaker":speaker,"part":"news","index":index})
                current = end
                clips.append(clip)
            segments.append({"kind":"news","index":index,"start":round(start,3),"end":round(current,3)})
        manifest = temp / "concat.txt"
        manifest.write_text("".join("file '%s'\n" % p for p in clips))
        output = audio_dir / (today + "-ja.mp3")
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
                        "-i",str(manifest),"-c:a","libmp3lame","-q:a","4",str(output)],check=True)
    episode = {"format":"monoradio/news-1","date":today,"lang":"ja","title":script["title"],
        "opening":[],"closing":[],"news":news,"seconds":round(duration(output),3),
        "lines_timed":lines,"segments":segments,"audio":"audio/"+output.name,
        "made_at":dt.datetime.now(dt.timezone.utc).isoformat()}
    dest.write_text(json.dumps(episode,ensure_ascii=False,indent=2)+"\n")
    listing = ROOT / "episodes.json"
    episodes = json.loads(listing.read_text())
    episodes = [x for x in episodes if x.get("date") != today]
    episodes.insert(0,{"date":today,"ja":{"title":episode["title"],"seconds":episode["seconds"]}})
    listing.write_text(json.dumps(episodes,ensure_ascii=False,indent=2)+"\n")
    print("Created",dest)

if __name__ == "__main__":
    main()
