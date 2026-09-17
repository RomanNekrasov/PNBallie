#!/usr/bin/env python3
"""Reusable OpenAI/Azure asset generator; see docs/ASSET_GENERATION.md."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path(__file__).with_name("asset_catalog.json")
MAX_RESPONSE_BYTES = 24 * 1024 * 1024


def read_catalog(path: Path) -> dict:
    catalog = json.loads(path.read_text())
    for section in ("assets", "styles"):
        if not catalog.get(section):
            raise ValueError(f"Catalogus mist {section}.")
        for key, value in catalog[section].items():
            if not re.fullmatch(r"[a-z][a-z0-9_-]*", key):
                raise ValueError(f"Ongeldige sleutel in {section}.")
            if not isinstance(value.get("prompt"), str) or not value["prompt"].strip():
                raise ValueError(f"Prompt ontbreekt: {key}.")
    return catalog


def configuration(provider: str, model: str | None, endpoint: str | None) -> dict:
    azure = provider == "azure"
    model = model or os.getenv("AZURE_OPENAI_IMAGE_DEPLOYMENT" if azure else "OPENAI_IMAGE_MODEL", "")
    if not model.strip():
        raise ValueError("Kies expliciet --model of stel het bestaande image-model in via de omgeving.")
    if azure:
        endpoint = (endpoint or os.getenv("AZURE_OPENAI_ENDPOINT", "")).rstrip("/")
        url = urlsplit(endpoint)
        if (url.scheme != "https" or not url.hostname
                or not url.hostname.endswith((".openai.azure.com", ".cognitiveservices.azure.com"))
                or url.username or url.password or url.port not in (None, 443)
                or url.path or url.query or url.fragment):
            raise ValueError("Stel een geldig Azure OpenAI HTTPS-endpoint in, zonder pad of credentials.")
        endpoint += "/openai/v1/images/generations?api-version=preview"
    else:
        if endpoint:
            raise ValueError("--endpoint is uitsluitend voor Azure.")
        endpoint = "https://api.openai.com/v1/images/generations"
    return {"provider": provider, "model": model, "url": endpoint}


def make_jobs(catalog: dict, assets: list[str], styles: list[str], config: dict, quality: str) -> list[dict]:
    jobs = []
    for asset_key in dict.fromkeys(assets):
        asset = catalog["assets"][asset_key]
        for style_key in dict.fromkeys(styles):
            style = catalog["styles"][style_key]
            prompt = "\n\n".join((
                catalog["shared_prompt"], style["prompt"],
                f"Asset title (context only): {asset['label']}. Meaning: {asset['description']}",
                f"Subject: {asset['prompt']}",
            ))
            payload = {"model": config["model"], "prompt": prompt, "size": "1024x1024",
                       "quality": quality, "background": "transparent", "output_format": "png", "n": 1}
            fingerprint = hashlib.sha256(json.dumps({"config": config, "payload": payload},
                                                   sort_keys=True).encode()).hexdigest()
            jobs.append({"asset": asset_key, "style": style_key, "label": asset["label"],
                         "style_label": style["label"], "resample": style.get("resample", "lanczos"),
                         "file": f"{asset_key}--{style_key}.png", "fingerprint": fingerprint,
                         "payload": payload})
    return jobs


def generate_image(config: dict, payload: dict, *, transport=None) -> tuple[bytes, dict]:
    azure = config["provider"] == "azure"
    key = os.getenv("AZURE_OPENAI_API_KEY" if azure else "OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("API-sleutel ontbreekt; stel deze lokaal in als omgevingsvariabele.")
    headers = {"api-key": key} if azure else {"Authorization": f"Bearer {key}"}
    try:
        # No automatic retries: a timed-out generation may already have been billed.
        with httpx.Client(timeout=httpx.Timeout(600, connect=15), follow_redirects=False,
                          transport=transport) as client:
            with client.stream("POST", config["url"], json=payload, headers=headers) as response:
                if response.status_code != 200:
                    raise ValueError(f"Image API gaf HTTP {response.status_code}; geen automatische herhaling.")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise ValueError("Modelantwoord is te groot.")
        result = json.loads(body)
        raw = base64.b64decode(result["data"][0]["b64_json"], validate=True)
    except httpx.TimeoutException:
        raise ValueError("Image API-timeout; mogelijk al gefactureerd. Niet automatisch herhaald.") from None
    except httpx.HTTPError:
        raise ValueError("Image API-netwerkfout; niet automatisch herhaald.") from None
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise ValueError("Modelantwoord bevat geen bruikbare base64-afbeelding.") from None
    return raw, {"usage": result.get("usage"), "created": result.get("created")}


def inspect_png(raw: bytes) -> dict:
    with Image.open(BytesIO(raw)) as source:
        if source.format != "PNG" or source.size != (1024, 1024):
            raise ValueError("Verwacht een PNG van 1024 bij 1024 pixels.")
        image = source.convert("RGBA")
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    total = image.width * image.height
    transparent = sum(histogram[:16]) / total
    opaque = sum(histogram[240:]) / total
    if transparent < .01 or opaque < .01:
        raise ValueError("Geen echte transparante achtergrond of geen zichtbaar icoon; bronbestand bewaard.")
    return {"size": list(image.size), "transparent_fraction": round(transparent, 4),
            "visible_bbox": alpha.point(lambda p: 255 if p >= 16 else 0).getbbox()}


def save_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def web_icon(raw: bytes) -> tuple[bytes, tuple[int, int, int, int]]:
    """Remove only near-transparent noise; keep enclosed whites and original colors."""
    inspect_png(raw)
    with Image.open(BytesIO(raw)) as source:
        image = source.convert("RGBA")
    image.putalpha(image.getchannel("A").point([0] * 16 + list(range(16, 256))))
    bounds = image.getbbox()
    if bounds is None:
        raise ValueError("Geen zichtbaar icoon om te exporteren.")
    image = image.crop(bounds)
    image.thumbnail((224, 224), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (256, 256))
    canvas.alpha_composite(image, ((256 - image.width) // 2, (256 - image.height) // 2))
    output = BytesIO()
    canvas.save(output, format="WEBP", lossless=True, method=6)
    return output.getvalue(), bounds


def export_assets(catalog: dict, source: Path, output: Path, style: str, keys: list[str]) -> None:
    manifest_path = output / "manifest.json"
    manifest = {"style": style, "style_label": catalog["styles"][style]["label"],
                "export": {"size": [256, 256], "visible_max": 224, "alpha_cutoff": 16, "lossless": True},
                "assets": {}}
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        if previous.get("style") != style:
            raise ValueError("De uitvoermap bevat een andere stijl; kies een aparte map.")
        manifest["assets"].update(previous["assets"])
    prepared = []
    # Validate the complete selection before writing any app asset.
    for key in keys:
        path = source / f"{key}--{style}.png"
        raw = path.read_bytes()
        metadata = json.loads(path.with_suffix(".json").read_text())
        digest = hashlib.sha256(raw).hexdigest()
        if (metadata.get("status") != "complete" or metadata.get("style") != style
                or metadata.get("asset") != key or metadata.get("sha256") != digest):
            raise ValueError(f"Geen geverifieerde bronafbeelding voor {key}.")
        encoded, bounds = web_icon(raw)
        prepared.append((key, encoded))
        manifest["assets"][key] = {
            "label": catalog["assets"][key]["label"], "source_file": path.name,
            "source_sha256": digest, "web_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_bounds": bounds, "provider": metadata["provider"], "model": metadata["model"],
            "prompt": metadata["payload"]["prompt"], "quality": metadata["payload"]["quality"],
        }
    output.mkdir(parents=True, exist_ok=True)
    for key, encoded in prepared:
        (output / f"{key}.webp").write_bytes(encoded)
        print(f"Geëxporteerd: {key}.webp ({len(encoded) // 1024} KiB)")
    save_json(manifest_path, manifest)


def run_job(job: dict, config: dict, output: Path, resume: bool) -> dict:
    target = output / job["file"]
    metadata = target.with_suffix(".json")
    if metadata.exists() or target.exists():
        previous = json.loads(metadata.read_text()) if metadata.exists() else {}
        if (resume and previous.get("status") == "complete"
                and previous.get("fingerprint") == job["fingerprint"] and target.exists()
                and hashlib.sha256(target.read_bytes()).hexdigest() == previous.get("sha256")):
            print(f"Behouden: {job['file']}", flush=True)
            return previous
        raise ValueError(f"{job['file']} bestaat of heeft een onzekere poging. Gebruik een nieuwe uitvoermap.")
    record = {**job, "provider": config["provider"], "model": config["model"],
              "started_at": datetime.now(UTC).isoformat(), "status": "started"}
    save_json(metadata, record)
    print(f"Genereren: {job['file']}", flush=True)
    try:
        raw, info = generate_image(config, job["payload"])
        # Keep the exact response image even when validation fails; never erase a paid result.
        with target.open("xb") as handle:
            handle.write(raw)
        record.update(info)
        record.update(inspect_png(raw))
        record.update(status="complete", sha256=hashlib.sha256(raw).hexdigest(),
                      finished_at=datetime.now(UTC).isoformat())
    except (ValueError, OSError) as exc:
        record["status"] = "failed"
        # Never persist raw HTTP exception bodies or authentication headers.
        record["error"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        save_json(metadata, record)
        raise ValueError(f"{job['file']}: {record['error']}") from None
    save_json(metadata, record)
    print(f"Gereed: {job['file']}", flush=True)
    return record


def gallery(output: Path, jobs: list[dict]) -> None:
    complete = [job for job in jobs if (output / job["file"]).exists()
                and json.loads((output / job["file"]).with_suffix(".json").read_text()).get("status") == "complete"]
    cards = []
    for job in complete:
        filename = html.escape(job["file"], quote=True)
        cards.append(f'<article><h2>{html.escape(job["label"])}</h2><p>{html.escape(job["style_label"])}</p>'
                     f'<a href="{filename}"><img class="large" src="{filename}" alt="{html.escape(job["label"], quote=True)}"></a>'
                     f'<div class="sizes"><span>32 px <img width="32" src="{filename}"></span>'
                     f'<span>48 px <img width="48" src="{filename}"></span>'
                     f'<span>96 px <img width="96" src="{filename}"></span></div>'
                     f'<details><summary>Volledige prompt</summary><pre>{html.escape(job["payload"]["prompt"])}</pre></details></article>')
    page = '''<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PNBallie · Assetstijl kiezen</title><style>
*{box-sizing:border-box}body{margin:0;padding:32px;background:#111927;color:#eff3fa;font:16px system-ui}
body.light{background:#eef1f5;color:#152132}h1{margin:0 0 10px}p{color:#93a6bc}body.light p{color:#43556b}
button{padding:10px 16px;border:1px solid #637995;border-radius:8px;cursor:pointer}
main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:28px}
article{background:#ffffff08;border:1px solid #60759055;border-radius:18px;padding:20px;min-width:0}
h2{font-size:20px;margin:0}.large{display:block;width:100%;max-width:320px;margin:auto}
.sizes{display:flex;align-items:center;justify-content:space-around;gap:12px;min-height:120px}
.sizes span{display:grid;justify-items:center;gap:10px;font-size:12px}pre{white-space:pre-wrap;font:12px/1.6 monospace}
summary{cursor:pointer;color:#8297b1}@media(max-width:760px){body{padding:16px}main{grid-template-columns:1fr}}
</style><h1>Kies een assetstijl</h1><p>Dezelfde onderwerpen in drie stijlen. Bekijk ook de kleine versies.</p>
<button onclick="document.body.classList.toggle('light')">Wissel lichte / donkere achtergrond</button><main>'''
    (output / "index.html").write_text(page + "".join(cards) + "</main></html>")
    if not complete:
        return
    styles = list(dict.fromkeys(job["style"] for job in jobs))
    assets = list(dict.fromkeys(job["asset"] for job in jobs))
    sheet = Image.new("RGB", (len(styles) * 360, 72 + len(assets) * 380), "#111927")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=19)
    small = ImageFont.load_default(size=14)
    for column, style in enumerate(styles):
        label = next(job["style_label"] for job in jobs if job["style"] == style)
        draw.text((column * 360 + 20, 24), label, font=font, fill="#f2f5fa")
    for job in complete:
        x, y = styles.index(job["style"]) * 360, 72 + assets.index(job["asset"]) * 380
        draw.rounded_rectangle((x + 8, y + 8, x + 352, y + 372), radius=16, fill="#1c2839")
        draw.text((x + 24, y + 20), job["label"], font=font, fill="#f2f5fa")
        with Image.open(output / job["file"]) as source:
            icon = source.convert("RGBA")
        resample = Image.Resampling.NEAREST if job["resample"] == "nearest" else Image.Resampling.LANCZOS
        large = icon.resize((260, 260), resample)
        sheet.paste(large, (x + 50, y + 48), large)
        for size, offset in ((32, 28), (48, 128), (64, 248)):
            thumb = icon.resize((size, size), resample)
            sheet.paste(thumb, (x + offset, y + 308), thumb)
            draw.text((x + offset + size + 4, y + 320), str(size), font=small, fill="#aebed0")
    sheet.save(output / "comparison.png")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "preview", "generate", "select", "export"])
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--provider", choices=["azure", "openai"], default="azure")
    parser.add_argument("--model")
    parser.add_argument("--endpoint")
    parser.add_argument("--assets", nargs="+")
    parser.add_argument("--style", help="Stijlsleutel uit de catalogus, bijvoorbeeld pixel, game3d of enamel.")
    parser.add_argument("--all", action="store_true", help="Genereer alle assets in de gekozen stijl.")
    parser.add_argument("--quality", choices=["low", "medium", "high", "auto"], default="high")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--input", type=Path, help="Bronmap met voltooide generaties voor export.")
    parser.add_argument("--concurrency", type=int, choices=range(1, 4), default=3)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Behoud alleen exact passende, voltooide resultaten.")
    args = parser.parse_args()
    catalog = read_catalog(args.catalog)
    if args.command == "list":
        print(json.dumps(catalog, ensure_ascii=False, indent=2))
        return 0
    if args.command == "select":
        if not args.style:
            parser.error("select vereist --style.")
        if args.style not in catalog["styles"]:
            parser.error("Onbekende stijl; voeg deze eerst toe aan de catalogus.")
        catalog["default_style"] = args.style
        if not args.dry_run:
            save_json(args.catalog, catalog)
        print(f"Standaardstijl: {args.style}")
        return 0
    if args.command == "export":
        style = args.style or catalog.get("default_style")
        keys = args.assets or list(catalog["assets"])
        if not args.input or not args.output or style not in catalog["styles"]:
            parser.error("export vereist --input, --output en een gekozen stijl.")
        if any(key not in catalog["assets"] for key in keys):
            parser.error("Onbekende asset in de exportselectie.")
        if args.dry_run:
            print(json.dumps({"style": style, "assets": keys}, ensure_ascii=False))
        else:
            export_assets(catalog, args.input, args.output, style, keys)
        return 0
    config = configuration(args.provider, args.model, args.endpoint)
    if args.command == "preview":
        assets = args.assets or catalog["preview_assets"]
        styles = list(catalog["styles"])
    else:
        assets = list(catalog["assets"]) if args.all else args.assets
        style = args.style or catalog.get("default_style")
        if not assets or not style:
            parser.error("generate vereist --assets/--all en --style (of eerst select).")
        styles = [style]
    if any(asset not in catalog["assets"] for asset in assets):
        parser.error("Onbekende asset; gebruik list of voeg deze toe aan de catalogus.")
    if any(style not in catalog["styles"] for style in styles):
        parser.error("Onbekende stijl in de catalogus.")
    jobs = make_jobs(catalog, assets, styles, config, args.quality)
    if args.dry_run:
        print(json.dumps({"config": config, "jobs": jobs}, ensure_ascii=False, indent=2))
        return 0
    key_name = "AZURE_OPENAI_API_KEY" if args.provider == "azure" else "OPENAI_API_KEY"
    if not os.getenv(key_name, "").strip():
        parser.error(f"Stel {key_name} lokaal in. Zet geen sleutel in de catalogus.")
    output = args.output or ROOT / "output/imagegen" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=args.resume)
    run_path = output / "run.json"
    run = {"config": config, "jobs": jobs}
    if run_path.exists() and json.loads(run_path.read_text()) != run:
        raise ValueError("Deze uitvoermap hoort bij een andere generatieopdracht; kies een nieuwe map.")
    save_json(run_path, run)
    failed = False
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(run_job, job, config, output, args.resume) for job in jobs]
        for future in as_completed(futures):
            try:
                future.result()
            except ValueError as exc:
                failed = True
                print(str(exc), file=sys.stderr, flush=True)
    gallery(output, jobs)
    print(f"Galerij: {output / 'index.html'}", flush=True)
    return int(failed)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
