#!/usr/bin/env python3
"""Build or validate a graph-bound locale catalog for a review projection.

The standard-library path creates and validates catalogs without translating.
Optional translation uses a caller-selected local Ollama or Argos adapter. The
canonical graph is never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}
CYRILLIC = re.compile(r"[А-Яа-яЁё]")
PROTECTED = re.compile(
    r"```[\s\S]*?```|`[^`]+`|https?://\S+|\[[ xX]\]|"
    r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]+|"
    r"\b(?:B\d{2}(?:-[A-Z]\d{2})?|C\d{2}|T-\d+)\b|"
    r"\b[a-z][a-z0-9]+(?:_[a-z0-9]+)+\b|"
    r"[A-Za-z0-9_./-]*[A-Za-z][A-Za-z0-9_./-]*(?:[ \t]+[A-Za-z0-9_./-]*[A-Za-z][A-Za-z0-9_./-]*)*"
)


def entry_id(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]


def displayed_strings(graph: dict) -> list[str]:
    """Return unique strings that the HTML renderer can present to a reviewer."""
    values: list[str] = []
    for block in graph.get("blocks", []):
        values.extend((block.get("title", ""), block.get("main_output", "")))
    for node in graph.get("nodes", []):
        values.append(node.get("title", ""))
        for contract_name in ("operational_fields", "artifact_contract"):
            for key, value in (node.get(contract_name) or {}).items():
                values.extend((key, value if isinstance(value, str) else str(value)))
    return list(dict.fromkeys(value for value in values if value))


def batches(items: list[tuple[str, str]], max_chars: int) -> list[list[tuple[str, str]]]:
    result: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    size = 0
    for item in items:
        item_size = len(item[1])
        if current and size + item_size > max_chars:
            result.append(current)
            current, size = [], 0
        current.append(item)
        size += item_size
    if current:
        result.append(current)
    return result


def ollama_translate(
    endpoint: str,
    model: str,
    target_name: str,
    items: list[tuple[str, str]],
    timeout: int,
) -> dict[str, str]:
    payload_items = [{"id": key, "text": text} for key, text in items]
    prompt = (
        f"Translate every text value from Russian to {target_name}. "
        "Return one JSON object whose keys are the supplied id values and whose values are translations. "
        "Preserve Markdown, backticks, file paths, identifiers such as B01-S01/C01, enum values, commands, "
        "and product names. Do not summarize, omit, explain, or add facts. JSON only.\n\n"
        + json.dumps(payload_items, ensure_ascii=False, separators=(",", ":"))
    )
    request_body = json.dumps(
        {
            "model": model,
            "stream": False,
            "format": "json",
            "keep_alive": "30m",
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": prompt}],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/api/chat",
        data=request_body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        outer = json.loads(response.read())
    translated = json.loads(outer["message"]["content"])
    expected = {key for key, _ in items}
    if set(translated) != expected or not all(isinstance(value, str) for value in translated.values()):
        raise ValueError("translator returned an incomplete or malformed id set")
    return translated


def translate_resilient(
    endpoint: str,
    model: str,
    target_name: str,
    items: list[tuple[str, str]],
    timeout: int,
) -> dict[str, str]:
    try:
        return ollama_translate(endpoint, model, target_name, items, timeout)
    except (ValueError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as error:
        if len(items) == 1:
            raise RuntimeError(f"cannot translate {items[0][0]}: {error}") from error
        midpoint = len(items) // 2
        print(f"retry_split target={target_name} items={len(items)} reason={type(error).__name__}", flush=True)
        return {
            **translate_resilient(endpoint, model, target_name, items[:midpoint], timeout),
            **translate_resilient(endpoint, model, target_name, items[midpoint:], timeout),
        }


def protect_literals(source: str) -> tuple[str, dict[str, str]]:
    literals: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        literal = match.group(0)
        suffix = ""
        while literal and literal[-1] in ".,;:!?":
            suffix = literal[-1] + suffix
            literal = literal[:-1]
        token = f"<x{len(literals)}>"
        literals[token] = literal
        return token + suffix

    return PROTECTED.sub(replace, source), literals


def restore_literals(translated: str, literals: dict[str, str]) -> str:
    for token, source in literals.items():
        if token not in translated:
            raise ValueError(f"translation lost protected literal {source!r}")
        translated = translated.replace(token, source)
    return translated


def argos_translate(source: str, locale: str) -> str:
    import argostranslate.translate  # type: ignore[import-not-found]

    translated_lines: list[str] = []
    in_fence = False
    for line in source.split("\n"):
        if line.lstrip().startswith("```"):
            translated_lines.append(line)
            in_fence = not in_fence
            continue
        if in_fence:
            translated_lines.append(line)
            continue
        if not line:
            translated_lines.append("")
            continue
        prefix_match = re.match(r"^(\s*(?:[-*•]|\d+[.)])\s+)", line)
        prefix = prefix_match.group(1) if prefix_match else ""
        content = line[len(prefix):]
        def translate_inline_code(match: re.Match[str]) -> str:
            inner = match.group(1)
            if not CYRILLIC.search(inner):
                return match.group(0)
            translated_inner = argostranslate.translate.translate(inner, "ru", locale)
            return "`" + translated_inner + "`"

        content = re.sub(r"`([^`]+)`", translate_inline_code, content)
        def translate_plain(plain: str) -> str:
            if not CYRILLIC.search(plain):
                return plain
            leading = re.match(r"^\s*", plain).group(0)
            trailing = re.search(r"\s*$", plain).group(0)
            end = len(plain) - len(trailing) if trailing else len(plain)
            core = plain[len(leading):end]
            return leading + argostranslate.translate.translate(core, "ru", locale) + trailing

        pieces: list[str] = []
        cursor = 0
        for match in PROTECTED.finditer(content):
            plain = content[cursor:match.start()]
            pieces.append(translate_plain(plain))
            pieces.append(match.group(0))
            cursor = match.end()
        tail = content[cursor:]
        pieces.append(translate_plain(tail))
        translated_lines.append(prefix + "".join(pieces))
    return "\n".join(translated_lines)


def load_or_create(
    graph_path: Path,
    output_path: Path,
    source_locale: str,
    target_locales: list[str],
) -> tuple[dict, dict]:
    graph_bytes = graph_path.read_bytes()
    graph = json.loads(graph_bytes)
    graph_hash = hashlib.sha256(graph_bytes).hexdigest()
    sources = displayed_strings(graph)
    entries = {
        entry_id(source): {"source": source, "translations": {source_locale: source}}
        for source in sources
    }
    existing: dict = {}
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        if existing.get("graph_sha256") == graph_hash and existing.get("source_locale") == source_locale:
            for key, entry in entries.items():
                prior = (existing.get("entries") or {}).get(key)
                if prior and prior.get("source") == entry["source"]:
                    entry["translations"].update(prior.get("translations") or {})
    catalog = {
        "schema_version": "1.0",
        "graph_id": graph["graph_id"],
        "graph_version": graph["graph_version"],
        "graph_sha256": graph_hash,
        "source_locale": source_locale,
        "locales": list(dict.fromkeys([source_locale, *target_locales])),
        "translation_provenance": existing.get("translation_provenance", {}),
        "entries": entries,
    }
    return graph, catalog


def validate_catalog(graph_path: Path, catalog_path: Path) -> dict:
    graph_bytes = graph_path.read_bytes()
    graph = json.loads(graph_bytes)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    graph_hash = hashlib.sha256(graph_bytes).hexdigest()
    if catalog.get("graph_id") != graph.get("graph_id"):
        errors.append("catalog graph_id does not match")
    if catalog.get("graph_sha256") != graph_hash:
        errors.append("catalog graph_sha256 does not match")
    locales = catalog.get("locales") or []
    if not locales or catalog.get("source_locale") not in locales:
        errors.append("catalog source locale is not present in locales")
    sources = displayed_strings(graph)
    for source in sources:
        key = entry_id(source)
        entry = (catalog.get("entries") or {}).get(key)
        if not entry or entry.get("source") != source:
            errors.append(f"missing visible string: {key}")
            continue
        missing = set(locales) - set(entry.get("translations") or {})
        if missing:
            errors.append(f"entry {key} is missing locales: {sorted(missing)}")
    return {"valid": not errors, "graph_sha256": graph_hash, "entries": len(sources), "locales": locales, "errors": errors}


def save_catalog(path: Path, catalog: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def provenance(provider: str, model: str) -> dict:
    if provider != "argos":
        return {"provider": f"ollama-local:{model}", "human_reviewed": False}
    import argostranslate.package  # type: ignore[import-not-found]

    packages = sorted(
        (
            package.from_code,
            package.to_code,
            str(package.package_version),
        )
        for package in argostranslate.package.get_installed_packages()
    )
    return {
        "provider": "argos-offline",
        "engine_version": importlib.metadata.version("argostranslate"),
        "packages": [
            {"from": source, "to": target, "version": version}
            for source, target, version in packages
        ],
        "human_reviewed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gemma4")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--provider", choices=("none", "ollama", "argos"), default="none")
    parser.add_argument("--source-locale", choices=("ru",), default="ru")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--locales", nargs="*", choices=sorted(LANGUAGES), default=[])
    parser.add_argument("--batch-chars", type=int, default=9000)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    graph_path = args.graph.resolve()
    output_path = args.output.resolve()
    if args.validate_only:
        report = validate_catalog(graph_path, output_path)
        print(json.dumps(report, ensure_ascii=False))
        raise SystemExit(0 if report["valid"] else 1)
    if args.provider == "none" and args.locales:
        parser.error("--locales requires --provider ollama or --provider argos")
    _, catalog = load_or_create(graph_path, output_path, args.source_locale, args.locales)
    save_catalog(output_path, catalog)

    if args.provider == "none":
        print(output_path)
        return

    total = len(catalog["entries"])
    method = provenance(args.provider, args.model)
    for locale in args.locales:
        catalog.setdefault("translation_provenance", {})[locale] = method
        pending = [
            (key, entry["source"])
            for key, entry in catalog["entries"].items()
            if (args.overwrite or locale not in entry["translations"]) and CYRILLIC.search(entry["source"])
        ]
        untouched = [
            (key, entry["source"])
            for key, entry in catalog["entries"].items()
            if locale not in entry["translations"] and not CYRILLIC.search(entry["source"])
        ]
        for key, source in untouched:
            catalog["entries"][key]["translations"][locale] = source
        if args.provider == "argos":
            print(f"locale={locale} provider=argos pending={len(pending)} total_entries={total}", flush=True)
            for index, (key, source) in enumerate(pending, 1):
                catalog["entries"][key]["translations"][locale] = argos_translate(source, locale)
                if index % 25 == 0 or index == len(pending):
                    save_catalog(output_path, catalog)
                    print(f"locale={locale} translated={index}/{len(pending)}", flush=True)
            continue
        work = batches(pending, args.batch_chars)
        print(f"locale={locale} pending={len(pending)} batches={len(work)} total_entries={total}", flush=True)
        for index, batch in enumerate(work, 1):
            started = time.monotonic()
            translated = translate_resilient(
                args.endpoint, args.model, LANGUAGES[locale], batch, args.timeout
            )
            for key, value in translated.items():
                catalog["entries"][key]["translations"][locale] = value
            save_catalog(output_path, catalog)
            print(
                f"locale={locale} batch={index}/{len(work)} items={len(batch)} "
                f"seconds={time.monotonic()-started:.1f}",
                flush=True,
            )
    save_catalog(output_path, catalog)
    print(output_path)


if __name__ == "__main__":
    main()
