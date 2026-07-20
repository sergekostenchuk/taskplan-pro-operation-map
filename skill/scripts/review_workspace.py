#!/usr/bin/env python3
"""Build a self-contained TASK-PLAN PRO operational-map review workspace."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path


SUPPORTED_UI_LOCALES = ("ru", "en", "es", "fr", "de")
REVIEW_STATUSES = {
    "unreviewed", "questions", "discussing", "decision_made",
    "change_required", "change_applied", "closed",
}
REVIEW_FIELDS = (
    "owner_observation", "owner_question", "owner_proposal",
    "reviewer_1", "reviewer_2",
)


def _script_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def displayed_strings(graph: dict) -> list[str]:
    values: list[str] = []
    for block in graph.get("blocks", []):
        values.extend((block.get("title", ""), block.get("main_output", "")))
    for node in graph.get("nodes", []):
        values.append(node.get("title", ""))
        for contract_name in ("operational_fields", "artifact_contract"):
            for key, value in (node.get(contract_name) or {}).items():
                values.extend((key, value if isinstance(value, str) else str(value)))
    return list(dict.fromkeys(value for value in values if value))


def default_catalog(graph: dict, graph_hash: str, source_locale: str = "en") -> dict:
    if source_locale not in SUPPORTED_UI_LOCALES:
        raise ValueError(f"unsupported UI locale: {source_locale}")
    entries = {}
    for source in displayed_strings(graph):
        key = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
        entries[key] = {"source": source, "translations": {source_locale: source}}
    return {
        "schema_version": "1.0",
        "graph_id": graph["graph_id"],
        "graph_version": graph["graph_version"],
        "graph_sha256": graph_hash,
        "source_locale": source_locale,
        "locales": [source_locale],
        "translation_provenance": {},
        "entries": entries,
    }


def default_presentation(graph: dict) -> dict:
    return {
        "schema_version": "1.0",
        "overview_groups": [{
            "id": "product_journey",
            "block_ids": [block["id"] for block in graph.get("blocks", [])],
            "labels": {
                "ru": "Путь продукта", "en": "Product journey",
                "es": "Recorrido del producto", "fr": "Parcours produit",
                "de": "Produktablauf",
            },
        }],
    }


def _validate_projection_inputs(graph: dict, i18n: dict, presentation: dict) -> None:
    locales = i18n.get("locales") or []
    if not locales or i18n.get("source_locale") not in locales:
        raise ValueError("translation catalog has no valid source locale")
    unsupported = set(locales) - set(SUPPORTED_UI_LOCALES)
    if unsupported:
        raise ValueError(f"unsupported UI locales: {sorted(unsupported)}")
    for key, entry in (i18n.get("entries") or {}).items():
        missing = set(locales) - set(entry.get("translations") or {})
        if missing:
            raise ValueError(f"translation entry {key} is missing locales: {sorted(missing)}")
    graph_block_ids = [block["id"] for block in graph.get("blocks", [])]
    grouped_ids = [
        block_id
        for group in presentation.get("overview_groups", [])
        for block_id in group.get("block_ids", [])
    ]
    if len(grouped_ids) != len(set(grouped_ids)) or set(grouped_ids) != set(graph_block_ids):
        raise ValueError("presentation groups must contain every graph block exactly once")
    feedback = presentation.get("feedback_transition")
    if feedback and {feedback.get("source"), feedback.get("target")} - set(graph_block_ids):
        raise ValueError("presentation feedback transition references an unknown block")


def _validate_review(review: dict, graph: dict, graph_hash: str) -> None:
    if review.get("graph_id") != graph.get("graph_id"):
        raise ValueError("review state belongs to another graph")
    if review.get("graph_sha256") != graph_hash:
        raise ValueError("review state does not match the canonical graph hash")
    if review.get("ui_locale", "en") not in SUPPORTED_UI_LOCALES:
        raise ValueError("review state contains an unsupported UI locale")
    names = review.get("reviewer_names")
    if not isinstance(names, dict) or not all(isinstance(names.get(key), str) for key in ("owner", "reviewer_1", "reviewer_2")):
        raise ValueError("review state has invalid reviewer names")
    annotations = review.get("annotations")
    if not isinstance(annotations, dict):
        raise ValueError("review state annotations must be an object")
    for node_id, annotation in annotations.items():
        if not isinstance(node_id, str) or not isinstance(annotation, dict):
            raise ValueError("review annotation has an invalid shape")
        if annotation.get("status", "unreviewed") not in REVIEW_STATUSES:
            raise ValueError(f"review annotation {node_id} has an invalid status")
        if not all(isinstance(annotation.get(field, ""), str) for field in REVIEW_FIELDS):
            raise ValueError(f"review annotation {node_id} has a non-string comment field")


def build(
    graph_path: Path,
    output_path: Path,
    i18n_path: Path | None = None,
    presentation_path: Path | None = None,
    review_path: Path | None = None,
    source_locale: str = "en",
) -> dict:
    graph_bytes = graph_path.read_bytes()
    graph = json.loads(graph_bytes)
    graph_hash = hashlib.sha256(graph_bytes).hexdigest()
    i18n = json.loads(i18n_path.read_text(encoding="utf-8")) if i18n_path and i18n_path.exists() else default_catalog(graph, graph_hash, source_locale)
    if i18n.get("graph_sha256") != graph_hash:
        raise ValueError("translation catalog does not match the canonical graph hash")
    presentation = json.loads(presentation_path.read_text(encoding="utf-8")) if presentation_path and presentation_path.exists() else default_presentation(graph)
    _validate_projection_inputs(graph, i18n, presentation)
    default_names = {
        "ru": ("Владелец продукта", "Коллега 1", "Коллега 2"),
        "en": ("Product owner", "Reviewer 1", "Reviewer 2"),
        "es": ("Responsable del producto", "Revisor 1", "Revisor 2"),
        "fr": ("Responsable produit", "Relecteur 1", "Relecteur 2"),
        "de": ("Product Owner", "Reviewer 1", "Reviewer 2"),
    }
    owner, reviewer_1, reviewer_2 = default_names[i18n["source_locale"]]
    initial_review = {
        "schema_version": "1.0",
        "graph_id": graph["graph_id"],
        "graph_version": graph["graph_version"],
        "graph_sha256": graph_hash,
        "updated_at": None,
        "ui_locale": i18n["source_locale"],
        "reviewer_names": {
            "owner": owner,
            "reviewer_1": reviewer_1,
            "reviewer_2": reviewer_2,
        },
        "annotations": {},
    }
    if review_path and review_path.exists():
        initial_review = json.loads(review_path.read_text(encoding="utf-8"))
    _validate_review(initial_review, graph, graph_hash)
    title = f"TASK-PLAN PRO · Операционная карта · {graph['graph_version']}"
    document = TEMPLATE.replace("__TITLE__", html.escape(title))
    document = document.replace("__GRAPH_JSON__", _script_json(graph))
    document = document.replace("__REVIEW_JSON__", _script_json(initial_review))
    document = document.replace("__I18N_JSON__", _script_json(i18n))
    document = document.replace("__PRESENTATION_JSON__", _script_json(presentation))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return {
        "graph_sha256": graph_hash,
        "html_sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
        "locales": i18n["locales"],
        "nodes": len(graph.get("nodes", [])),
        "blocks": len(graph.get("blocks", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--i18n", type=Path)
    parser.add_argument("--presentation", type=Path)
    parser.add_argument("--review-state", type=Path)
    parser.add_argument("--source-locale", choices=SUPPORTED_UI_LOCALES, default="en")
    args = parser.parse_args()
    result = build(
        args.graph.resolve(), args.output.resolve(),
        args.i18n.resolve() if args.i18n else None,
        args.presentation.resolve() if args.presentation else None,
        args.review_state.resolve() if args.review_state else None,
        args.source_locale,
    )
    print(json.dumps({"output": str(args.output.resolve()), **result}, ensure_ascii=False))


TEMPLATE = r'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>__TITLE__</title>
  <style>
    :root {
      --bg:#07101f;--panel:#0d1729;--panel2:#111e34;--line:#263652;--text:#edf4ff;
      --muted:#94a5bf;--cyan:#20d5ff;--green:#2ae6a0;--amber:#ffbd4a;--red:#ff6577;
      --purple:#c779ff;--blue:#679cff;--focus:#fff;--shadow:0 18px 50px #0007;
      --radius:14px;--top:68px;--left:286px;--right:390px;
    }
    *{box-sizing:border-box}html,body{height:100%;margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    button,input,select,textarea{font:inherit;color:inherit}button{cursor:pointer}
    :focus-visible{outline:2px solid var(--focus);outline-offset:2px}.sr-only{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
    .topbar{height:var(--top);display:flex;align-items:center;gap:14px;padding:10px 18px;border-bottom:1px solid var(--line);background:#081223ee;backdrop-filter:blur(12px);position:fixed;inset:0 0 auto;z-index:20}
    .brand{min-width:250px}.brand strong{font-size:16px;letter-spacing:.02em}.brand small{display:block;color:var(--muted)}
    .search{flex:1;max-width:620px;position:relative}.search input{width:100%;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 38px 10px 12px}.search kbd{position:absolute;right:10px;top:9px;color:var(--muted);border:1px solid var(--line);border-radius:5px;padding:1px 5px}
    .toolbar{margin-left:auto;display:flex;gap:8px;align-items:center}.btn{border:1px solid var(--line);background:var(--panel2);padding:9px 11px;border-radius:9px;white-space:nowrap}.btn:hover{border-color:#58719b}.btn.primary{background:#0d5364;border-color:var(--cyan)}.btn.success{background:#164c3a;border-color:var(--green)}.btn:disabled{opacity:.45;cursor:not-allowed}.dirty{color:var(--amber);font-size:12px;min-width:90px;text-align:right}.dirty.saved{color:var(--green)}
    .sidebar{position:fixed;top:var(--top);bottom:0;left:0;width:var(--left);border-right:1px solid var(--line);background:#091426;padding:14px;overflow:auto;z-index:10}.side-title{display:flex;justify-content:space-between;align-items:center;margin:4px 2px 10px}.side-title h2{font-size:12px;color:var(--muted);letter-spacing:.12em;text-transform:uppercase;margin:0}.block-nav{display:grid;gap:5px}.block-link{width:100%;display:grid;grid-template-columns:38px 1fr auto;align-items:center;gap:8px;text-align:left;background:transparent;border:1px solid transparent;border-radius:10px;padding:8px}.block-link:hover{background:var(--panel);border-color:var(--line)}.block-link.selected{background:#12233b;border-color:var(--cyan)}.block-id{color:var(--cyan);font-weight:700}.block-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.badge{border-radius:999px;background:#1d2b40;color:var(--muted);font-size:11px;padding:2px 7px}.badge.attention{color:#171006;background:var(--amber)}
    .filters{margin-top:16px;border-top:1px solid var(--line);padding-top:14px;display:grid;gap:9px}.filters label{font-size:12px;color:var(--muted)}.filters select,.filters input{width:100%;margin-top:4px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px}.privacy-note{margin-top:18px;color:var(--muted);font-size:11px;border:1px solid var(--line);border-radius:10px;padding:10px}
    main{position:fixed;top:var(--top);bottom:0;left:var(--left);right:var(--right);overflow:auto;padding:20px}.view{max-width:1500px;margin:auto}.view-header{display:flex;align-items:flex-start;gap:14px;margin-bottom:16px}.view-header h1{font-size:22px;margin:0 0 5px}.view-header p{margin:0;color:var(--muted);max-width:900px}.view-actions{margin-left:auto;display:flex;gap:7px}
    .metrics{display:grid;grid-template-columns:repeat(4,minmax(130px,1fr));gap:10px;margin-bottom:16px}.metric{border:1px solid var(--line);background:var(--panel);border-radius:12px;padding:12px}.metric strong{display:block;font-size:22px}.metric span{color:var(--muted);font-size:12px}
    .overview-panel{padding:0;overflow:hidden}.overview-head{display:flex;align-items:center;gap:12px;padding:12px 14px;border-bottom:1px solid var(--line)}.overview-head h2{font-size:14px;margin:0}.overview-modes{margin-left:auto;display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}.overview-modes button{border:0;border-left:1px solid var(--line);background:#0b1729;padding:7px 10px}.overview-modes button:first-child{border-left:0}.overview-modes button.active{background:#155166;color:#fff}.overview-wrap{height:min(68vh,720px);min-height:560px;position:relative;overflow:hidden;background-color:#050b15;background-image:linear-gradient(#17223855 1px,transparent 1px),linear-gradient(90deg,#17223855 1px,transparent 1px);background-size:24px 24px}.overview-wrap svg{width:100%;height:100%;touch-action:none}.overview-lane{fill:#0a1527;stroke:#263652;stroke-width:1.5;rx:18}.overview-lane-label{fill:#8fa6c9;font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase}.overview-node{cursor:pointer}.overview-node rect{fill:#101d31;stroke:#3d5679;stroke-width:1.5;rx:12}.overview-node:hover rect,.overview-node:focus rect{stroke:var(--cyan);stroke-width:2.5}.overview-node .overview-id{fill:var(--cyan);font-size:12px;font-weight:800}.overview-node .overview-title{fill:var(--text);font-size:13px;font-weight:700}.overview-node .overview-copy{fill:var(--muted);font-size:10px}.overview-node .overview-status{fill:#0a1424;stroke:#314665;rx:8}.overview-node .overview-status-text{fill:#b8c8df;font-size:9px}.overview-node .overview-progress-bg{fill:#1a2940}.overview-node .overview-progress{fill:var(--green)}.overview-edge{fill:none;stroke:var(--cyan);stroke-width:2;opacity:.8}.overview-edge.secondary{stroke:#536987;stroke-width:1.2;opacity:.45}.overview-edge.failure{stroke:var(--red);stroke-dasharray:6 5}.overview-edge.feedback{stroke:var(--purple);stroke-dasharray:7 5}.overview-tooltip{position:absolute;display:none;max-width:330px;background:#07111fee;border:1px solid var(--cyan);border-radius:9px;padding:8px 10px;font-size:11px;pointer-events:none;box-shadow:var(--shadow);z-index:4}.overview-tooltip.show{display:block}.progress{height:5px;background:#17253a;border-radius:99px;margin-top:12px;overflow:hidden}.progress i{display:block;height:100%;background:var(--green)}
    .panel{border:1px solid var(--line);background:var(--panel);border-radius:var(--radius);padding:14px;box-shadow:var(--shadow)}.panel-title{display:flex;align-items:center;gap:8px;margin-bottom:10px}.panel-title h2{font-size:15px;margin:0}.legend{margin-left:auto;display:flex;flex-wrap:wrap;gap:9px;color:var(--muted);font-size:11px}.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:4px}
    .graph-wrap{height:min(62vh,670px);min-height:420px;position:relative;overflow:hidden;border-radius:10px;background-color:#050b15;background-image:linear-gradient(#17223855 1px,transparent 1px),linear-gradient(90deg,#17223855 1px,transparent 1px);background-size:24px 24px}.graph-wrap svg{width:100%;height:100%;touch-action:none}.graph-controls{position:absolute;right:10px;top:10px;display:flex;gap:5px;z-index:2}.graph-controls button{width:34px;height:34px;border:1px solid var(--line);background:#0c1729dd;border-radius:8px}.edge{fill:none;stroke:#425b7f;stroke-width:1.4;opacity:.6}.edge.failure{stroke:var(--red);stroke-dasharray:5 4}.edge.success{stroke:var(--green)}.edge.produces{stroke:var(--cyan)}.node rect{fill:#101d31;stroke:#496181;stroke-width:1.5;rx:10}.node text{fill:var(--text);font-size:11px;pointer-events:none}.node .node-id{fill:var(--muted);font-size:9px;font-weight:700}.node.step rect{stroke:var(--blue)}.node.artifact rect{stroke:var(--green)}.node.gate rect,.node.decision rect{stroke:var(--amber)}.node.failure rect{stroke:var(--red)}.node.selected rect{stroke:var(--focus);stroke-width:3}.node.has-review rect{filter:drop-shadow(0 0 5px var(--amber))}.node{cursor:pointer}
    .node-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;margin-top:12px}.node-row{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;border:1px solid var(--line);background:#0d182a;border-radius:9px;padding:9px;text-align:left}.node-row:hover,.node-row.selected{border-color:var(--cyan)}.type-icon{width:9px;height:9px;border-radius:3px;background:var(--blue)}.type-icon.artifact{background:var(--green);border-radius:50%}.type-icon.failure{background:var(--red)}.type-icon.gate,.type-icon.decision{background:var(--amber);transform:rotate(45deg)}
    .inspector{position:fixed;top:var(--top);bottom:0;right:0;width:var(--right);border-left:1px solid var(--line);background:#091426;overflow:auto;padding:16px;z-index:10;transition:transform .2s}.inspector.collapsed{transform:translateX(100%)}body.inspector-collapsed main{right:0}.inspector-empty{color:var(--muted);display:grid;place-items:center;height:70%;text-align:center;padding:30px}.inspector h2{font-size:18px;margin:5px 0}.node-meta{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 14px}.pill{font-size:11px;border:1px solid var(--line);color:var(--muted);padding:3px 7px;border-radius:999px}.fields{display:grid;gap:10px}.field label{display:block;color:var(--muted);font-size:12px;margin-bottom:5px}.field textarea{width:100%;min-height:78px;resize:vertical;border:1px solid var(--line);background:#07111f;border-radius:9px;padding:9px}.field textarea:focus{border-color:var(--cyan)}.field.owner textarea{border-left:3px solid var(--cyan)}.field.review textarea{border-left:3px solid var(--purple)}.status-row{display:grid;grid-template-columns:1fr auto;gap:8px;margin:12px 0}.status-row select{background:#07111f;border:1px solid var(--line);border-radius:8px;padding:8px}.details{margin:12px 0}.details summary{cursor:pointer;color:var(--cyan)}.details dl{display:grid;grid-template-columns:125px 1fr;gap:6px 10px;font-size:12px}.details dt{color:var(--muted)}.details dd{margin:0;white-space:pre-wrap}.discussion{white-space:pre-wrap;background:#06101d;border:1px solid var(--line);padding:10px;border-radius:9px;font-size:12px;max-height:220px;overflow:auto}.language-select{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:9px 8px}.translation-badge{font-size:10px;color:var(--amber);border:1px solid #8a682b;border-radius:999px;padding:2px 5px}.translation-badge[hidden]{display:none}
    .toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);background:#14243b;border:1px solid var(--green);border-radius:10px;padding:10px 14px;opacity:0;pointer-events:none;transition:.2s;z-index:50}.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
    .modal{position:fixed;inset:0;background:#000a;display:none;place-items:center;z-index:60;padding:20px}.modal.open{display:grid}.modal-card{width:min(620px,100%);max-height:85vh;overflow:auto;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}.modal-card h2{margin-top:0}.modal-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:15px}.help-list{color:var(--muted)}
    .empty-state,.error-state{padding:50px 20px;text-align:center;color:var(--muted)}.error-state{color:var(--red)}.orphan-warning{margin-top:14px;border:1px solid var(--amber);background:#3a2e1233;border-radius:10px;padding:11px;color:#ffd687}.name-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.name-grid label{color:var(--muted);font-size:12px}.name-grid input{width:100%;margin-top:4px;background:#07111f;border:1px solid var(--line);border-radius:8px;padding:8px}
    @media(max-width:1100px){:root{--right:340px;--left:230px}.brand{min-width:auto}.brand small{display:none}.toolbar .secondary-label{display:none}}
    @media(max-width:820px){:root{--top:196px}.topbar{height:var(--top);flex-wrap:wrap;align-content:flex-start}.brand{width:100%}.toolbar{order:2;width:100%;margin:0;gap:5px;overflow-x:auto;padding-bottom:3px}.toolbar .dirty{display:none}.search{order:3;max-width:none;width:100%}.sidebar{display:none}main{left:0;right:0;padding:12px}.inspector{inset:var(--top) 0 0 0;width:auto;display:none}.inspector.mobile-open{display:block;transform:none}.metrics{grid-template-columns:repeat(2,1fr)}.view-header{flex-wrap:wrap}.view-actions{margin-left:0}.btn{padding:8px}.graph-wrap{height:50vh;min-height:360px}.overview-wrap{height:62vh;min-height:480px}.overview-head{align-items:flex-start;flex-wrap:wrap}.overview-modes{margin-left:0}}
    @media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand"><strong>TASK-PLAN PRO</strong><small id="versionLine">Операционная карта</small></div>
    <div class="search"><label class="sr-only" for="searchInput">Поиск по карте</label><input id="searchInput" placeholder="Найти блок, шаг, gate, failure…" autocomplete="off"><kbd>/</kbd></div>
    <div class="toolbar">
      <label class="sr-only" for="languageSelect">Language</label>
      <select id="languageSelect" class="language-select" aria-label="Language"><option value="ru">RU</option><option value="en">EN</option><option value="es">ES</option><option value="fr">FR</option><option value="de">DE</option></select>
      <span id="translationBadge" class="translation-badge" hidden>MT</span>
      <span id="saveState" class="dirty saved">Сохранено локально</span>
      <button class="btn" id="importButton" type="button">Импорт</button>
      <button class="btn" id="exportButton" type="button">JSON</button>
      <button class="btn success" id="saveHtmlButton" type="button"><span class="secondary-label">Сохранить </span>HTML</button>
      <button class="btn" id="helpButton" type="button" aria-label="Справка">?</button>
      <input id="importFile" type="file" accept="application/json,.json" hidden>
    </div>
  </header>

  <aside class="sidebar" aria-label="Навигация по блокам">
    <div class="side-title"><h2 id="blocksTitle">Блоки</h2><button class="btn" id="overviewButton" type="button">Обзор</button></div>
    <nav id="blockNav" class="block-nav"></nav>
    <div class="filters">
      <label><span id="typeFilterLabel">Тип узла</span><select id="typeFilter"><option value="all">Все типы</option></select></label>
      <label><span id="implementationFilterLabel">Статус реализации</span><select id="implementationFilter"><option value="all">Все статусы</option></select></label>
      <label><span id="reviewFilterLabel">Статус ревью</span><select id="reviewFilter"><option value="all">Все статусы</option><option value="attention">Требуют внимания</option><option value="with_comments">Есть комментарии</option></select></label>
      <button class="btn primary" id="nextButton" type="button">Следующий для ревью</button>
    </div>
    <div id="privacyNote" class="privacy-note">Файл работает локально и ничего не отправляет наружу. Автосохранение хранится в браузере. Для переноса комментариев сохраните HTML или экспортируйте JSON.</div>
  </aside>

  <main id="main" tabindex="-1"><div id="appView" class="view"><div class="empty-state" data-state="loading">Загрузка карты…</div></div></main>
  <aside id="inspector" class="inspector" aria-label="Карточка узла"><div class="inspector-empty">Выберите блок или узел карты, чтобы прочитать контракт и оставить комментарии.</div></aside>
  <div id="toast" class="toast" role="status" aria-live="polite"></div>

  <div id="helpModal" class="modal" role="dialog" aria-modal="true" aria-labelledby="helpTitle">
    <div class="modal-card">
      <h2 id="helpTitle">Как проводить ревью</h2>
      <ol id="helpList" class="help-list">
        <li>Откройте блок, затем узел на схеме или в списке.</li>
        <li>Заполните три поля владельца и два поля коллег-рецензентов.</li>
        <li>Назначьте статус. Автосохранение работает только в текущем браузере.</li>
        <li>Кнопка «Сохранить HTML» скачивает новую автономную копию со встроенными комментариями. Исходный файл браузер сам перезаписать не может.</li>
        <li>JSON нужен для обмена и слияния комментариев без копирования всего HTML.</li>
      </ol>
      <p id="helpNote">Комментарий не становится требованием или задачей автоматически. Решение фиксируется статусом «Решение принято», после чего изменение отдельно применяется к каноническому графу.</p>
      <h3 id="reviewerNamesTitle">Имена рецензентов</h3>
      <div class="name-grid"><label><span id="reviewer1Label">Рецензент 1</span><input id="reviewer1Name" autocomplete="off"></label><label><span id="reviewer2Label">Рецензент 2</span><input id="reviewer2Name" autocomplete="off"></label></div>
      <div class="modal-actions"><button class="btn primary" id="closeHelp" type="button">Понятно</button></div>
    </div>
  </div>

  <script id="graph-data" type="application/json">__GRAPH_JSON__</script>
  <script id="review-data" type="application/json">__REVIEW_JSON__</script>
  <script id="i18n-data" type="application/json">__I18N_JSON__</script>
  <script id="presentation-data" type="application/json">__PRESENTATION_JSON__</script>
  <script>
  (() => {
    'use strict';
    const $ = (s, root=document) => root.querySelector(s);
    const $$ = (s, root=document) => [...root.querySelectorAll(s)];
    const esc = value => String(value ?? '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
    const graph = JSON.parse($('#graph-data').textContent);
    const embeddedReview = JSON.parse($('#review-data').textContent);
    const contentCatalog = JSON.parse($('#i18n-data').textContent);
    const presentation = JSON.parse($('#presentation-data').textContent);
    const storageKey = `task-plan-pro-review:${graph.graph_id}:${graph.graph_version}:${embeddedReview.graph_sha256}`;
    const UI = {
      ru:{map:'Операционная карта',saved:'Сохранено локально',saving:'Сохранение…',import:'Импорт',save:'Сохранить',help:'Справка',blocks:'Блоки',overview:'Обзор',search:'Найти блок, шаг, gate, failure…',node_type:'Тип узла',impl_status:'Статус реализации',review_status:'Статус ревью',all_types:'Все типы',all_statuses:'Все статусы',attention:'Требуют внимания',with_comments:'Есть комментарии',next_review:'Следующий для ревью',privacy:'Файл работает локально и ничего не отправляет наружу. Автосохранение хранится в браузере. Для переноса комментариев сохраните HTML или экспортируйте JSON.',overview_title:'Операционная карта продукта',overview_intro:'Крупный путь от исходного замысла до релиза и следующего цикла обучения. Откройте блок для детализации.',main_pipeline:'Главный путь',all_relations:'Все связи',how_read:'Как читать карту',how_read_text:'Каждый блок раскрывается в рабочий граф шагов, артефактов, gates, решений и failure-маршрутов. Комментарии привязаны к стабильному ID, а не к позиции текста.',nodes_canon:'узлов в каноне',reviewed:'просмотрено / прокомментировано',need_attention:'требуют внимания',closed_metric:'закрыто',no_results:'По текущим фильтрам ничего не найдено. Сбросьте поиск или фильтры.',all_blocks:'Все блоки',next_node:'Следующий узел',block_graph:'Граф блока',step:'шаг',artifact:'артефакт',failure:'провал',select_node:'Выберите узел карты.',node_contract:'Контракт узла',implements:'Реализует',no_trace:'нет traceability',copy:'Копировать',owner_observation:'Комментарий / наблюдение',owner_question:'Вопрос для обсуждения',owner_proposal:'Предложение / вариант решения',empty_comment:'Оставьте пустым, если комментария нет',reviewer_1:'Коллега 1',reviewer_2:'Коллега 2',product_input:'Вход',product_output:'Выход',design:'Дизайн',gates:'Gates',feedback:'Обратная связь',review_progress:'Ревью',fit:'Вписать',zoom_in:'Увеличить',zoom_out:'Уменьшить'},
      en:{map:'Operational map',saved:'Saved locally',saving:'Saving…',import:'Import',save:'Save',help:'Help',blocks:'Blocks',overview:'Overview',search:'Find a block, step, gate, failure…',node_type:'Node type',impl_status:'Implementation status',review_status:'Review status',all_types:'All types',all_statuses:'All statuses',attention:'Needs attention',with_comments:'Has comments',next_review:'Next for review',privacy:'This file works locally and sends nothing outside. Autosave stays in this browser. Save HTML or export JSON to move comments.',overview_title:'Product operational map',overview_intro:'The large path from the initial intent to release and the next learning cycle. Open a block to drill down.',main_pipeline:'Main pipeline',all_relations:'All relations',how_read:'How to read the map',how_read_text:'Each block opens into a working graph of steps, artifacts, gates, decisions, and failure routes. Comments bind to stable IDs, not text positions.',nodes_canon:'nodes in canon',reviewed:'reviewed / commented',need_attention:'need attention',closed_metric:'closed',no_results:'Nothing matches the current filters. Reset search or filters.',all_blocks:'All blocks',next_node:'Next node',block_graph:'Block graph',step:'step',artifact:'artifact',failure:'failure',select_node:'Select a map node.',node_contract:'Node contract',implements:'Implements',no_trace:'no traceability',copy:'Copy',owner_observation:'Comment / observation',owner_question:'Question for discussion',owner_proposal:'Proposal / solution option',empty_comment:'Leave empty if there is no comment',reviewer_1:'Reviewer 1',reviewer_2:'Reviewer 2',product_input:'Input',product_output:'Output',design:'Design',gates:'Gates',feedback:'Feedback',review_progress:'Review',fit:'Fit',zoom_in:'Zoom in',zoom_out:'Zoom out'},
      es:{map:'Mapa operativo',saved:'Guardado localmente',saving:'Guardando…',import:'Importar',save:'Guardar',help:'Ayuda',blocks:'Bloques',overview:'Resumen',search:'Buscar bloque, paso, gate, fallo…',node_type:'Tipo de nodo',impl_status:'Estado de implementación',review_status:'Estado de revisión',all_types:'Todos los tipos',all_statuses:'Todos los estados',attention:'Requiere atención',with_comments:'Con comentarios',next_review:'Siguiente para revisar',privacy:'El archivo funciona localmente y no envía nada al exterior. El autoguardado permanece en este navegador. Guarde HTML o exporte JSON para trasladar comentarios.',overview_title:'Mapa operativo del producto',overview_intro:'El recorrido completo desde la idea inicial hasta el lanzamiento y el siguiente ciclo de aprendizaje. Abra un bloque para ver el detalle.',main_pipeline:'Flujo principal',all_relations:'Todas las relaciones',how_read:'Cómo leer el mapa',how_read_text:'Cada bloque se abre en un grafo de pasos, artefactos, gates, decisiones y rutas de fallo. Los comentarios se vinculan a ID estables.',nodes_canon:'nodos en el canon',reviewed:'revisados / comentados',need_attention:'requieren atención',closed_metric:'cerrados',no_results:'Nada coincide con los filtros actuales.',all_blocks:'Todos los bloques',next_node:'Siguiente nodo',block_graph:'Grafo del bloque',step:'paso',artifact:'artefacto',failure:'fallo',select_node:'Seleccione un nodo del mapa.',node_contract:'Contrato del nodo',implements:'Implementa',no_trace:'sin trazabilidad',copy:'Copiar',owner_observation:'Comentario / observación',owner_question:'Pregunta para debatir',owner_proposal:'Propuesta / opción de solución',empty_comment:'Déjelo vacío si no hay comentario',reviewer_1:'Revisor 1',reviewer_2:'Revisor 2',product_input:'Entrada',product_output:'Salida',design:'Diseño',gates:'Gates',feedback:'Retroalimentación',review_progress:'Revisión',fit:'Ajustar',zoom_in:'Acercar',zoom_out:'Alejar'},
      fr:{map:'Carte opérationnelle',saved:'Enregistré localement',saving:'Enregistrement…',import:'Importer',save:'Enregistrer',help:'Aide',blocks:'Blocs',overview:'Vue générale',search:'Rechercher un bloc, une étape, un gate, un échec…',node_type:'Type de nœud',impl_status:'État de mise en œuvre',review_status:'État de revue',all_types:'Tous les types',all_statuses:'Tous les états',attention:'À examiner',with_comments:'Avec commentaires',next_review:'Prochain à revoir',privacy:'Le fichier fonctionne localement et ne transmet rien. La sauvegarde automatique reste dans ce navigateur. Enregistrez le HTML ou exportez le JSON pour déplacer les commentaires.',overview_title:'Carte opérationnelle du produit',overview_intro:'Le parcours complet de l’intention initiale à la mise en production et au cycle d’apprentissage suivant. Ouvrez un bloc pour le détail.',main_pipeline:'Parcours principal',all_relations:'Toutes les relations',how_read:'Comment lire la carte',how_read_text:'Chaque bloc s’ouvre en graphe de travail : étapes, artefacts, gates, décisions et routes d’échec. Les commentaires sont liés à des ID stables.',nodes_canon:'nœuds dans le canon',reviewed:'revus / commentés',need_attention:'à examiner',closed_metric:'clos',no_results:'Aucun résultat avec les filtres actuels.',all_blocks:'Tous les blocs',next_node:'Nœud suivant',block_graph:'Graphe du bloc',step:'étape',artifact:'artefact',failure:'échec',select_node:'Sélectionnez un nœud de la carte.',node_contract:'Contrat du nœud',implements:'Met en œuvre',no_trace:'sans traçabilité',copy:'Copier',owner_observation:'Commentaire / observation',owner_question:'Question à discuter',owner_proposal:'Proposition / option de solution',empty_comment:'Laisser vide en l’absence de commentaire',reviewer_1:'Relecteur 1',reviewer_2:'Relecteur 2',product_input:'Entrée',product_output:'Sortie',design:'Conception',gates:'Gates',feedback:'Retour',review_progress:'Revue',fit:'Ajuster',zoom_in:'Agrandir',zoom_out:'Réduire'},
      de:{map:'Betriebslandkarte',saved:'Lokal gespeichert',saving:'Speichern…',import:'Importieren',save:'Speichern',help:'Hilfe',blocks:'Blöcke',overview:'Übersicht',search:'Block, Schritt, Gate oder Fehler suchen…',node_type:'Knotentyp',impl_status:'Umsetzungsstatus',review_status:'Reviewstatus',all_types:'Alle Typen',all_statuses:'Alle Status',attention:'Benötigt Aufmerksamkeit',with_comments:'Mit Kommentaren',next_review:'Nächster Review',privacy:'Die Datei arbeitet lokal und sendet nichts nach außen. Die automatische Speicherung bleibt in diesem Browser. Speichern Sie HTML oder exportieren Sie JSON, um Kommentare zu übertragen.',overview_title:'Operative Produktlandkarte',overview_intro:'Der vollständige Weg von der ersten Absicht bis zum Release und zum nächsten Lernzyklus. Öffnen Sie einen Block für Details.',main_pipeline:'Hauptablauf',all_relations:'Alle Beziehungen',how_read:'So lesen Sie die Karte',how_read_text:'Jeder Block öffnet einen Arbeitsgraphen mit Schritten, Artefakten, Gates, Entscheidungen und Fehlerwegen. Kommentare sind an stabile IDs gebunden.',nodes_canon:'Knoten im Kanon',reviewed:'geprüft / kommentiert',need_attention:'benötigen Aufmerksamkeit',closed_metric:'geschlossen',no_results:'Keine Treffer für die aktuellen Filter.',all_blocks:'Alle Blöcke',next_node:'Nächster Knoten',block_graph:'Blockgraph',step:'Schritt',artifact:'Artefakt',failure:'Fehler',select_node:'Wählen Sie einen Kartenknoten.',node_contract:'Knotenvertrag',implements:'Implementiert',no_trace:'keine Rückverfolgbarkeit',copy:'Kopieren',owner_observation:'Kommentar / Beobachtung',owner_question:'Diskussionsfrage',owner_proposal:'Vorschlag / Lösungsoption',empty_comment:'Leer lassen, wenn kein Kommentar vorliegt',reviewer_1:'Reviewer 1',reviewer_2:'Reviewer 2',product_input:'Eingang',product_output:'Ausgang',design:'Design',gates:'Gates',feedback:'Rückkopplung',review_progress:'Review',fit:'Einpassen',zoom_in:'Vergrößern',zoom_out:'Verkleinern'}
    };
    const HELP = {
      ru:{title:'Как проводить ревью',steps:['Откройте блок, затем узел на схеме или в списке.','Заполните три поля владельца и два поля коллег-рецензентов.','Назначьте статус. Автосохранение работает только в текущем браузере.','«Сохранить HTML» скачивает автономную копию со встроенными комментариями.','JSON нужен для обмена и слияния комментариев без копирования всего HTML.'],note:'Комментарий не становится требованием автоматически. После статуса «Решение принято» изменение отдельно применяется к каноническому графу.',names:'Имена рецензентов',reviewer1:'Рецензент 1',reviewer2:'Рецензент 2',close:'Понятно'},
      en:{title:'How to review',steps:['Open a block, then select a node in the graph or list.','Complete the three owner fields and two peer-review fields.','Set a status. Autosave works only in this browser.','Save HTML downloads a self-contained copy with embedded comments.','Use JSON to exchange and merge comments without copying the full HTML.'],note:'A comment does not become a requirement automatically. After “Decision made”, apply the change separately to the canonical graph.',names:'Reviewer names',reviewer1:'Reviewer 1',reviewer2:'Reviewer 2',close:'Got it'},
      es:{title:'Cómo realizar la revisión',steps:['Abra un bloque y seleccione un nodo en el grafo o la lista.','Complete los tres campos del propietario y los dos de los revisores.','Asigne un estado. El autoguardado funciona solo en este navegador.','Guardar HTML descarga una copia autónoma con los comentarios integrados.','Use JSON para intercambiar y combinar comentarios sin copiar todo el HTML.'],note:'Un comentario no se convierte automáticamente en requisito. Tras “Decisión tomada”, el cambio se aplica por separado al grafo canónico.',names:'Nombres de revisores',reviewer1:'Revisor 1',reviewer2:'Revisor 2',close:'Entendido'},
      fr:{title:'Comment effectuer la revue',steps:['Ouvrez un bloc, puis sélectionnez un nœud dans le graphe ou la liste.','Renseignez les trois champs du propriétaire et les deux champs des relecteurs.','Attribuez un état. La sauvegarde automatique ne fonctionne que dans ce navigateur.','Enregistrer le HTML télécharge une copie autonome avec les commentaires intégrés.','Utilisez JSON pour échanger et fusionner les commentaires sans copier tout le HTML.'],note:'Un commentaire ne devient pas automatiquement une exigence. Après « Décision prise », appliquez séparément la modification au graphe canonique.',names:'Noms des relecteurs',reviewer1:'Relecteur 1',reviewer2:'Relecteur 2',close:'Compris'},
      de:{title:'So führen Sie das Review durch',steps:['Öffnen Sie einen Block und wählen Sie danach einen Knoten im Graphen oder in der Liste.','Füllen Sie die drei Owner-Felder und die zwei Reviewer-Felder aus.','Vergeben Sie einen Status. Die automatische Speicherung gilt nur für diesen Browser.','HTML speichern lädt eine eigenständige Kopie mit eingebetteten Kommentaren herunter.','JSON dient zum Austausch und Zusammenführen von Kommentaren ohne die gesamte HTML-Datei.'],note:'Ein Kommentar wird nicht automatisch zur Anforderung. Nach „Entscheidung getroffen“ wird die Änderung separat auf den kanonischen Graphen angewendet.',names:'Reviewer-Namen',reviewer1:'Reviewer 1',reviewer2:'Reviewer 2',close:'Verstanden'}
    };
    const MSG = {
      ru:{save_error:'Ошибка автосохранения',save_error_detail:'Браузер не смог сохранить черновик локально',copied:'Пакет узла скопирован',clipboard_error:'Буфер обмена недоступен — выделите поля вручную',scope_closed:'Все узлы в выбранной области закрыты',json_exported:'Review JSON экспортирован',html_saved:'Автономный HTML сохранён',wrong_graph:'Файл относится к другому графу',different_graph:'Версия графа отличается. Импортировать совпадающие ID и показать осиротевшие комментарии?',imported:'Комментарии импортированы по ID',import_failed:'Импорт не выполнен',read_failed:'Не удалось прочитать файл',nodes:'узла',blocks:'блоков',open_failed:'Не удалось открыть карту',integrity:'Проверьте целостность встроенного JSON или пересоберите HTML из канонического графа.'},
      en:{save_error:'Autosave error',save_error_detail:'The browser could not save the draft locally',copied:'Node package copied',clipboard_error:'Clipboard unavailable — select the fields manually',scope_closed:'All nodes in the selected scope are closed',json_exported:'Review JSON exported',html_saved:'Self-contained HTML saved',wrong_graph:'The file belongs to another graph',different_graph:'The graph version differs. Import matching IDs and show orphan annotations?',imported:'Comments imported by ID',import_failed:'Import failed',read_failed:'Could not read the file',nodes:'nodes',blocks:'blocks',open_failed:'Could not open the map',integrity:'Check the embedded JSON integrity or rebuild the HTML from the canonical graph.'},
      es:{save_error:'Error de autoguardado',save_error_detail:'El navegador no pudo guardar el borrador localmente',copied:'Paquete del nodo copiado',clipboard_error:'Portapapeles no disponible — seleccione los campos manualmente',scope_closed:'Todos los nodos del ámbito seleccionado están cerrados',json_exported:'Review JSON exportado',html_saved:'HTML autónomo guardado',wrong_graph:'El archivo pertenece a otro grafo',different_graph:'La versión del grafo es distinta. ¿Importar los ID coincidentes y mostrar comentarios huérfanos?',imported:'Comentarios importados por ID',import_failed:'Error de importación',read_failed:'No se pudo leer el archivo',nodes:'nodos',blocks:'bloques',open_failed:'No se pudo abrir el mapa',integrity:'Compruebe el JSON integrado o reconstruya el HTML desde el grafo canónico.'},
      fr:{save_error:'Erreur de sauvegarde automatique',save_error_detail:'Le navigateur n’a pas pu enregistrer le brouillon localement',copied:'Paquet du nœud copié',clipboard_error:'Presse-papiers indisponible — sélectionnez les champs manuellement',scope_closed:'Tous les nœuds de la zone sélectionnée sont clos',json_exported:'Review JSON exporté',html_saved:'HTML autonome enregistré',wrong_graph:'Le fichier appartient à un autre graphe',different_graph:'La version du graphe diffère. Importer les ID correspondants et afficher les commentaires orphelins ?',imported:'Commentaires importés par ID',import_failed:'Échec de l’import',read_failed:'Impossible de lire le fichier',nodes:'nœuds',blocks:'blocs',open_failed:'Impossible d’ouvrir la carte',integrity:'Vérifiez le JSON intégré ou reconstruisez le HTML depuis le graphe canonique.'},
      de:{save_error:'Fehler beim automatischen Speichern',save_error_detail:'Der Browser konnte den Entwurf nicht lokal speichern',copied:'Knotenpaket kopiert',clipboard_error:'Zwischenablage nicht verfügbar — Felder manuell auswählen',scope_closed:'Alle Knoten im gewählten Bereich sind geschlossen',json_exported:'Review-JSON exportiert',html_saved:'Eigenständiges HTML gespeichert',wrong_graph:'Die Datei gehört zu einem anderen Graphen',different_graph:'Die Graphversion weicht ab. Übereinstimmende IDs importieren und verwaiste Kommentare anzeigen?',imported:'Kommentare nach ID importiert',import_failed:'Import fehlgeschlagen',read_failed:'Datei konnte nicht gelesen werden',nodes:'Knoten',blocks:'Blöcke',open_failed:'Karte konnte nicht geöffnet werden',integrity:'Prüfen Sie das eingebettete JSON oder erstellen Sie das HTML aus dem kanonischen Graphen neu.'}
    };
    const MT_NOTE={ru:'Исходный язык',en:'Offline machine translation; human review is pending',es:'Traducción automática sin conexión; revisión humana pendiente',fr:'Traduction automatique hors ligne ; revue humaine en attente',de:'Offline-Maschinenübersetzung; menschliche Prüfung steht aus'};
    const STATUS = {ru:{unreviewed:'Не просмотрено',questions:'Есть вопросы',discussing:'Обсуждается',decision_made:'Решение принято',change_required:'Нужно изменение',change_applied:'Изменение внесено',closed:'Закрыто'},en:{unreviewed:'Unreviewed',questions:'Questions',discussing:'Discussing',decision_made:'Decision made',change_required:'Change required',change_applied:'Change applied',closed:'Closed'},es:{unreviewed:'Sin revisar',questions:'Preguntas',discussing:'En discusión',decision_made:'Decisión tomada',change_required:'Cambio necesario',change_applied:'Cambio aplicado',closed:'Cerrado'},fr:{unreviewed:'Non revu',questions:'Questions',discussing:'En discussion',decision_made:'Décision prise',change_required:'Modification requise',change_applied:'Modification appliquée',closed:'Clos'},de:{unreviewed:'Ungeprüft',questions:'Fragen',discussing:'In Diskussion',decision_made:'Entscheidung getroffen',change_required:'Änderung erforderlich',change_applied:'Änderung umgesetzt',closed:'Geschlossen'}};
    const TYPES = {ru:{block:'Блок',step:'Шаг',artifact:'Артефакт',gate:'Gate',decision:'Решение',failure:'Провал',terminal:'Терминал',external_reference:'Внешняя ссылка'},en:{block:'Block',step:'Step',artifact:'Artifact',gate:'Gate',decision:'Decision',failure:'Failure',terminal:'Terminal',external_reference:'External reference'},es:{block:'Bloque',step:'Paso',artifact:'Artefacto',gate:'Gate',decision:'Decisión',failure:'Fallo',terminal:'Terminal',external_reference:'Referencia externa'},fr:{block:'Bloc',step:'Étape',artifact:'Artefact',gate:'Gate',decision:'Décision',failure:'Échec',terminal:'Terminal',external_reference:'Référence externe'},de:{block:'Block',step:'Schritt',artifact:'Artefakt',gate:'Gate',decision:'Entscheidung',failure:'Fehler',terminal:'Terminal',external_reference:'Externe Referenz'}};
    const IMPL = {ru:{implemented:'Реализовано',partially_implemented:'Частично',designed_only:'Только спроектировано',not_applicable:'Не применимо'},en:{implemented:'Implemented',partially_implemented:'Partly implemented',designed_only:'Designed only',not_applicable:'Not applicable'},es:{implemented:'Implementado',partially_implemented:'Parcialmente implementado',designed_only:'Solo diseñado',not_applicable:'No aplicable'},fr:{implemented:'Mis en œuvre',partially_implemented:'Partiellement mis en œuvre',designed_only:'Conçu uniquement',not_applicable:'Sans objet'},de:{implemented:'Umgesetzt',partially_implemented:'Teilweise umgesetzt',designed_only:'Nur entworfen',not_applicable:'Nicht anwendbar'}};
    const reviewStatuses=new Set(['unreviewed','questions','discussing','decision_made','change_required','change_applied','closed']);
    const reviewFields=['owner_observation','owner_question','owner_proposal','reviewer_1','reviewer_2'];
    const contentBySource = new Map(Object.values(contentCatalog.entries||{}).map(entry=>[entry.source,entry.translations||{}]));
    let locale = embeddedReview.ui_locale && UI[embeddedReview.ui_locale] ? embeddedReview.ui_locale : 'ru';
    let statusLabels = STATUS[locale], typeLabels = TYPES[locale], implLabels = IMPL[locale];
    const t = key => UI[locale][key] || UI.ru[key] || key;
    const m = key => MSG[locale][key] || MSG.ru[key] || key;
    const tc = value => {const source=String(value??''), translations=contentBySource.get(source);return translations?.[locale] || translations?.ru || source};
    const nodes = graph.nodes || [];
    const blocks = [...(graph.blocks || [])].sort((a,b)=>a.order-b.order);
    const nodeById = new Map(nodes.map(n=>[n.id,n]));
    const childrenByParent = new Map();
    nodes.forEach(n => { if(n.parent_id){ const list=childrenByParent.get(n.parent_id)||[]; list.push(n); childrenByParent.set(n.parent_id,list); } });
    childrenByParent.forEach(list=>list.sort((a,b)=>a.id.localeCompare(b.id,undefined,{numeric:true})));
    let review = loadReview();
    let selectedBlock = null, selectedNode = null, viewMode = 'overview', dirty = false, saveTimer = null;
    if(review.ui_locale && UI[review.ui_locale]){locale=review.ui_locale;statusLabels=STATUS[locale];typeLabels=TYPES[locale];implLabels=IMPL[locale]}

    function loadReview(){
      try {
        const local = JSON.parse(localStorage.getItem(storageKey));
        if(local && local.graph_sha256 === embeddedReview.graph_sha256){
          const localTime = Date.parse(local.updated_at||0), embeddedTime = Date.parse(embeddedReview.updated_at||0);
          if(localTime > embeddedTime) return local;
        }
      } catch (_) {}
      return JSON.parse(JSON.stringify(embeddedReview));
    }
    function annotation(id, create=false){
      if(!review.annotations[id] && create) review.annotations[id] = {owner_observation:'',owner_question:'',owner_proposal:'',reviewer_1:'',reviewer_2:'',status:'unreviewed',updated_at:null};
      return review.annotations[id] || {owner_observation:'',owner_question:'',owner_proposal:'',reviewer_1:'',reviewer_2:'',status:'unreviewed',updated_at:null};
    }
    function hasText(a){ return ['owner_observation','owner_question','owner_proposal','reviewer_1','reviewer_2'].some(k=>(a[k]||'').trim()); }
    function needsAttention(a){ return ['questions','discussing','change_required'].includes(a.status) || !!(a.owner_question||'').trim(); }
    function touch(id){
      const a=annotation(id,true); a.updated_at=new Date().toISOString(); review.updated_at=a.updated_at; dirty=true;
      $('#saveState').textContent=t('saving'); $('#saveState').classList.remove('saved');
      clearTimeout(saveTimer); saveTimer=setTimeout(saveLocal,350);
    }
    function saveLocal(){
      try { localStorage.setItem(storageKey,JSON.stringify(review)); dirty=false; $('#saveState').textContent=t('saved'); $('#saveState').classList.add('saved'); }
      catch(e){ $('#saveState').textContent=m('save_error'); $('#saveState').classList.remove('saved'); toast(m('save_error_detail')); }
      renderNav(); renderMetricsOnly();
    }
    function toast(message){ const el=$('#toast'); el.textContent=message; el.classList.add('show'); clearTimeout(el._timer); el._timer=setTimeout(()=>el.classList.remove('show'),2600); }
    function download(name, content, mime){ const blob=new Blob([content],{type:mime}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000); }
    function reviewStats(){
      const values=nodes.map(n=>annotation(n.id));
      return {total:nodes.length, reviewed:values.filter(a=>a.status!=='unreviewed'||hasText(a)).length, attention:values.filter(needsAttention).length, closed:values.filter(a=>a.status==='closed').length};
    }
    function blockStats(id){ const list=[nodeById.get(id),...(childrenByParent.get(id)||[])].filter(Boolean); const reviewed=list.filter(n=>{const a=annotation(n.id);return a.status!=='unreviewed'||hasText(a)}).length; return {total:list.length,reviewed,attention:list.filter(n=>needsAttention(annotation(n.id))).length}; }
    function renderNav(){
      $('#blockNav').innerHTML=blocks.map(b=>{const s=blockStats(b.id);return `<button class="block-link ${selectedBlock===b.id?'selected':''}" data-block="${esc(b.id)}" type="button"><span class="block-id">${esc(b.id)}</span><span class="block-name">${esc(tc(b.title))}</span><span class="badge ${s.attention?'attention':''}">${s.reviewed}/${s.total}</span></button>`}).join('');
      $$('.block-link').forEach(btn=>btn.addEventListener('click',()=>openBlock(btn.dataset.block)));
    }
    function setupFilters(){
      const values={type:$('#typeFilter').value||'all',impl:$('#implementationFilter').value||'all',review:$('#reviewFilter').value||'all'};
      const types=[...new Set(nodes.map(n=>n.type))].sort();
      $('#typeFilter').innerHTML = `<option value="all">${esc(t('all_types'))}</option>`+types.map(type=>`<option value="${esc(type)}">${esc(typeLabels[type]||type)}</option>`).join('');
      const impl=[...new Set(nodes.map(n=>n.implementation_status))].sort();
      $('#implementationFilter').innerHTML = `<option value="all">${esc(t('all_statuses'))}</option>`+impl.map(status=>`<option value="${esc(status)}">${esc(implLabels[status]||status)}</option>`).join('');
      $('#reviewFilter').innerHTML = `<option value="all">${esc(t('all_statuses'))}</option><option value="attention">${esc(t('attention'))}</option><option value="with_comments">${esc(t('with_comments'))}</option>`+Object.entries(statusLabels).map(([value,label])=>`<option value="${value}">${esc(label)}</option>`).join('');
      $('#typeFilter').value=[...$('#typeFilter').options].some(o=>o.value===values.type)?values.type:'all';$('#implementationFilter').value=[...$('#implementationFilter').options].some(o=>o.value===values.impl)?values.impl:'all';$('#reviewFilter').value=[...$('#reviewFilter').options].some(o=>o.value===values.review)?values.review:'all';
    }
    function applyStaticI18n(){
      document.title=`TASK-PLAN PRO · ${t('map')} · ${graph.graph_version}`;
      $('#versionLine').textContent=`${graph.graph_version} · ${nodes.length} ${m('nodes')} · ${blocks.length} ${m('blocks')}`;
      const badge=$('#translationBadge');badge.hidden=locale==='ru';badge.title=MT_NOTE[locale];
      const help=HELP[locale];document.documentElement.lang=locale;$('#languageSelect').value=locale;$('#searchInput').placeholder=t('search');$('#saveState').textContent=dirty?t('saving'):t('saved');$('#importButton').textContent=t('import');$('#saveHtmlButton').innerHTML=`<span class="secondary-label">${esc(t('save'))} </span>HTML`;$('#helpButton').setAttribute('aria-label',t('help'));$('#blocksTitle').textContent=t('blocks');$('#overviewButton').textContent=t('overview');$('#typeFilterLabel').textContent=t('node_type');$('#implementationFilterLabel').textContent=t('impl_status');$('#reviewFilterLabel').textContent=t('review_status');$('#nextButton').textContent=t('next_review');$('#privacyNote').textContent=t('privacy');$('#helpTitle').textContent=help.title;$('#helpList').innerHTML=help.steps.map(step=>`<li>${esc(step)}</li>`).join('');$('#helpNote').textContent=help.note;$('#reviewerNamesTitle').textContent=help.names;$('#reviewer1Label').textContent=help.reviewer1;$('#reviewer2Label').textContent=help.reviewer2;$('#closeHelp').textContent=help.close;setupFilters();
    }
    function changeLocale(next){if(!UI[next])return;const generic1=new Set(Object.values(HELP).map(value=>value.reviewer1).concat('Коллега 1')),generic2=new Set(Object.values(HELP).map(value=>value.reviewer2).concat('Коллега 2'));if(generic1.has(review.reviewer_names.reviewer_1))review.reviewer_names.reviewer_1=HELP[next].reviewer1;if(generic2.has(review.reviewer_names.reviewer_2))review.reviewer_names.reviewer_2=HELP[next].reviewer2;locale=next;statusLabels=STATUS[locale];typeLabels=TYPES[locale];implLabels=IMPL[locale];review.ui_locale=locale;review.updated_at=new Date().toISOString();dirty=true;saveLocal();applyStaticI18n();$('#reviewer1Name').value=review.reviewer_names.reviewer_1;$('#reviewer2Name').value=review.reviewer_names.reviewer_2;renderNav();viewMode==='overview'?renderOverview():renderBlock();if(selectedNode)renderInspector()}
    function matchNode(n){
      const q=$('#searchInput').value.trim().toLocaleLowerCase(locale);
      const type=$('#typeFilter').value, impl=$('#implementationFilter').value, rs=$('#reviewFilter').value, a=annotation(n.id);
      const translatedFields=Object.entries(n.operational_fields||{}).map(([k,v])=>`${tc(k)} ${tc(v)}`).join(' ');
      if(q && !(`${n.id} ${n.title} ${tc(n.title)} ${JSON.stringify(n.operational_fields||{})} ${translatedFields}`).toLocaleLowerCase(locale).includes(q)) return false;
      if(type!=='all'&&n.type!==type) return false;
      if(impl!=='all'&&n.implementation_status!==impl) return false;
      if(rs==='attention'&&!needsAttention(a)) return false;
      if(rs==='with_comments'&&!hasText(a)) return false;
      if(rs!=='all'&&!['attention','with_comments'].includes(rs)&&a.status!==rs) return false;
      return true;
    }
    function metricsHtml(){ const s=reviewStats(); return `<div class="metrics" id="metrics"><div class="metric"><strong>${s.total}</strong><span>${esc(t('nodes_canon'))}</span></div><div class="metric"><strong>${s.reviewed}</strong><span>${esc(t('reviewed'))}</span></div><div class="metric"><strong>${s.attention}</strong><span>${esc(t('need_attention'))}</span></div><div class="metric"><strong>${s.closed}</strong><span>${esc(t('closed_metric'))}</span></div></div>`; }
    function renderMetricsOnly(){ const old=$('#metrics'); if(old) old.outerHTML=metricsHtml(); }
    function renderOverview(){
      viewMode='overview';selectedBlock=null;selectedNode=null;document.body.classList.add('inspector-collapsed');$('#inspector').classList.add('collapsed');renderNav();
      const visible=blocks.filter(b=>matchNode(nodeById.get(b.id))||(childrenByParent.get(b.id)||[]).some(matchNode));
      const orphanIds=Object.keys(review.annotations||{}).filter(id=>!nodeById.has(id));
      $('#appView').innerHTML=`<div class="view-header"><div><h1>${esc(t('overview_title'))}</h1><p>${esc(t('overview_intro'))}</p></div></div>${metricsHtml()}${visible.length?`<section class="panel overview-panel"><div class="overview-head"><h2>${esc(t('overview_title'))}</h2><div class="overview-modes" role="group" aria-label="Relations"><button id="mainPipelineMode" class="active" type="button">${esc(t('main_pipeline'))}</button><button id="allRelationsMode" type="button">${esc(t('all_relations'))}</button></div></div><div class="overview-wrap"><div class="graph-controls"><button id="overviewZoomIn" type="button" aria-label="${esc(t('zoom_in'))}">+</button><button id="overviewZoomOut" type="button" aria-label="${esc(t('zoom_out'))}">−</button><button id="overviewZoomFit" type="button" aria-label="${esc(t('fit'))}">⌂</button></div><svg id="overviewGraph" role="img" aria-label="${esc(t('overview_title'))}"></svg><div id="overviewTooltip" class="overview-tooltip" role="tooltip"></div></div></section><div class="panel" style="margin-top:14px"><div class="panel-title"><h2>${esc(t('how_read'))}</h2></div><p>${esc(t('how_read_text'))}</p>${orphanIds.length?`<div class="orphan-warning"><strong>${orphanIds.length} orphan annotations</strong><br>${orphanIds.map(esc).join(', ')}</div>`:''}</div>`:`<div class="empty-state">${esc(t('no_results'))}</div>`}`;
      if(visible.length) renderOverviewSvg(visible);
    }
    let overviewView=null, overviewRelationMode='main';
    function blockOf(nodeId){const node=nodeById.get(nodeId);return node?.type==='block'?node.id:node?.parent_id||null}
    function short(value,max){const text=String(value||'');return text.length>max?text.slice(0,max-1)+'…':text}
    function renderOverviewSvg(visible){
      const svg=$('#overviewGraph'), visibleIds=new Set(visible.map(block=>block.id));
      const configured=(presentation.overview_groups||[]).map(group=>({...group,block_ids:(group.block_ids||[]).filter(id=>visibleIds.has(id))})).filter(group=>group.block_ids.length);
      const assigned=new Set(configured.flatMap(group=>group.block_ids));
      const missing=visible.filter(block=>!assigned.has(block.id));
      if(missing.length) configured.push({id:'other',block_ids:missing.map(block=>block.id),labels:{ru:'Прочее',en:'Other',es:'Otros',fr:'Autres',de:'Weitere'}});
      const card={w:270,h:142}, lane={x:24,w:1130,h:188}, startX=190, gapX=305, positions=new Map();
      configured.forEach((group,row)=>group.block_ids.forEach((id,column)=>positions.set(id,{x:startX+column*gapX,y:26+row*lane.h+34,row,column})));
      const width=1180, height=Math.max(560,configured.length*lane.h+28);
      const laneMarkup=configured.map((group,row)=>`<g><rect class="overview-lane" x="${lane.x}" y="${18+row*lane.h}" width="${lane.w}" height="${lane.h-12}"></rect><text class="overview-lane-label" x="${lane.x+18}" y="${47+row*lane.h}">${esc(group.labels?.[locale]||group.labels?.ru||group.id)}</text></g>`).join('');
      const mainEdges=[];
      visible.forEach(block=>{if(block.next_block&&visibleIds.has(block.next_block))mainEdges.push({source:block.id,target:block.next_block,relation:'main'})});
      const feedback=presentation.feedback_transition||{};if(visibleIds.has(feedback.source)&&visibleIds.has(feedback.target))mainEdges.push({source:feedback.source,target:feedback.target,relation:'feedback'});
      const aggregate=new Map();
      (graph.edges||[]).forEach(edge=>{const source=blockOf(edge.source),target=blockOf(edge.target);if(!source||!target||source===target||!visibleIds.has(source)||!visibleIds.has(target))return;const key=`${source}|${target}|${edge.relation}`;aggregate.set(key,{source,target,relation:edge.relation})});
      const extras=[...aggregate.values()].filter(edge=>!mainEdges.some(main=>main.source===edge.source&&main.target===edge.target));
      const drawEdge=(edge,index,secondary=false)=>{const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)return'';const failure=/failure|return/.test(edge.relation),feedbackEdge=edge.relation==='feedback';let d;if(feedbackEdge){d=`M ${a.x} ${a.y+card.h/2} C 118 ${a.y+card.h/2}, 118 ${a.y+card.h/2}, 118 ${a.y+card.h/2} L 118 ${b.y+card.h/2} C 118 ${b.y+card.h/2}, 145 ${b.y+card.h/2}, ${b.x} ${b.y+card.h/2}`}else if(a.row===b.row){d=`M ${a.x+card.w} ${a.y+card.h/2} C ${a.x+card.w+34} ${a.y+card.h/2}, ${b.x-34} ${b.y+card.h/2}, ${b.x} ${b.y+card.h/2}`}else{const offset=18+(index%8)*8;d=`M ${a.x+card.w/2} ${a.y+card.h} C ${a.x+card.w/2+offset} ${a.y+card.h+45}, ${b.x+card.w/2-offset} ${b.y-45}, ${b.x+card.w/2} ${b.y}`}return `<path class="overview-edge ${secondary?'secondary':''} ${failure?'failure':''} ${feedbackEdge?'feedback':''}" d="${d}" marker-end="url(#overviewArrow)"><title>${esc(edge.relation)}</title></path>`};
      const edgeMarkup=mainEdges.map((edge,index)=>drawEdge(edge,index)).join('')+(overviewRelationMode==='all'?extras.map((edge,index)=>drawEdge(edge,index,true)).join(''):'');
      const feedbackLabel=mainEdges.some(edge=>edge.relation==='feedback')?`<text class="overview-lane-label" x="102" y="${height/2}" text-anchor="middle" transform="rotate(-90 102 ${height/2})">${esc(t('feedback'))}</text>`:'';
      const cards=visible.map(block=>{const p=positions.get(block.id);if(!p)return'';const stats=blockStats(block.id),pct=stats.total?Math.round(100*stats.reviewed/stats.total):0,children=childrenByParent.get(block.id)||[],gateCount=children.filter(n=>n.type==='gate'||n.type==='decision').length,previous=blocks.find(item=>item.next_block===block.id),input=previous?.main_output||t('product_input'),title=tc(block.title),output=tc(block.main_output||''),transition=block.next_block?`${output} → ${tc(nodeById.get(block.next_block)?.title||block.next_block)}`:`${output} → ${t('feedback')}`;return `<g class="overview-node" data-block="${esc(block.id)}" transform="translate(${p.x} ${p.y})" tabindex="0" role="button" aria-label="${esc(block.id+' '+title)}"><title>${esc(transition)}</title><rect width="${card.w}" height="${card.h}"></rect><text class="overview-id" x="14" y="22">${esc(block.id)}</text><text class="overview-title" x="14" y="44">${esc(short(title,32))}</text><text class="overview-copy" x="14" y="67">${esc(t('product_input'))}: ${esc(short(tc(input),34))}</text><text class="overview-copy" x="14" y="84">${esc(t('product_output'))}: ${esc(short(output,32))}</text><rect class="overview-status" x="14" y="96" width="154" height="22"></rect><text class="overview-status-text" x="22" y="111">${esc(short(implLabels[block.implementation_status]||block.implementation_status,24))}</text><text class="overview-status-text" x="178" y="111">${esc(t('gates'))} ${gateCount}</text><rect class="overview-progress-bg" x="14" y="127" width="242" height="5" rx="3"></rect><rect class="overview-progress" x="14" y="127" width="${242*pct/100}" height="5" rx="3"></rect><text class="overview-status-text" x="214" y="122">${pct}%</text></g>`}).join('');
      svg.innerHTML=`<defs><marker id="overviewArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#20d5ff"></path></marker></defs>${laneMarkup}${edgeMarkup}${feedbackLabel}${cards}`;
      overviewView={x:0,y:0,w:width,h:height,baseW:width,baseH:height};applyOverviewView();
      $$('.overview-node',svg).forEach(el=>{const block=nodeById.get(el.dataset.block),tooltip=$('#overviewTooltip');const show=e=>{tooltip.textContent=block.next_block?`${tc(block.main_output||'')} → ${tc(nodeById.get(block.next_block)?.title||block.next_block)}`:`${tc(block.main_output||'')} → ${t('feedback')}`;tooltip.style.left=`${Math.min(e.offsetX+16,svg.clientWidth-340)}px`;tooltip.style.top=`${Math.min(e.offsetY+16,svg.clientHeight-80)}px`;tooltip.classList.add('show')};el.addEventListener('mousemove',show);el.addEventListener('mouseleave',()=>tooltip.classList.remove('show'));el.addEventListener('click',()=>openBlock(el.dataset.block));el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openBlock(el.dataset.block)}})});
      $('#mainPipelineMode').classList.toggle('active',overviewRelationMode==='main');$('#allRelationsMode').classList.toggle('active',overviewRelationMode==='all');
      $('#mainPipelineMode').onclick=()=>{overviewRelationMode='main';renderOverviewSvg(visible)};$('#allRelationsMode').onclick=()=>{overviewRelationMode='all';renderOverviewSvg(visible)};
      $('#overviewZoomIn').onclick=()=>zoomOverview(.82);$('#overviewZoomOut').onclick=()=>zoomOverview(1.22);$('#overviewZoomFit').onclick=()=>{overviewView={x:0,y:0,w:width,h:height,baseW:width,baseH:height};applyOverviewView()};
      svg.addEventListener('wheel',e=>{e.preventDefault();zoomOverview(e.deltaY>0?1.1:.9)},{passive:false});enablePan(svg,()=>overviewView,value=>{overviewView=value;applyOverviewView()});
    }
    function zoomOverview(f){if(!overviewView)return;const nw=Math.max(420,Math.min(overviewView.baseW*3,overviewView.w*f)),nh=overviewView.h*(nw/overviewView.w);overviewView.x+=(overviewView.w-nw)/2;overviewView.y+=(overviewView.h-nh)/2;overviewView.w=nw;overviewView.h=nh;applyOverviewView()}
    function applyOverviewView(){if(overviewView)$('#overviewGraph').setAttribute('viewBox',`${overviewView.x} ${overviewView.y} ${overviewView.w} ${overviewView.h}`)}
    function enablePan(svg,getView,setView){let start=null;svg.addEventListener('pointerdown',e=>{if(e.target.closest('.overview-node,.node'))return;start={x:e.clientX,y:e.clientY,view:{...getView()}};svg.setPointerCapture(e.pointerId)});svg.addEventListener('pointermove',e=>{if(!start)return;const rect=svg.getBoundingClientRect(),v=start.view;setView({...v,x:v.x-(e.clientX-start.x)*v.w/rect.width,y:v.y-(e.clientY-start.y)*v.h/rect.height})});svg.addEventListener('pointerup',()=>start=null);svg.addEventListener('pointercancel',()=>start=null)}
    function openBlock(id){ selectedBlock=id;viewMode='block';document.body.classList.remove('inspector-collapsed');$('#inspector').classList.remove('collapsed');renderNav();renderBlock();selectNode(id);$('#main').focus(); }
    function renderBlock(){
      if(!selectedBlock) return renderOverview();
      const block=nodeById.get(selectedBlock), all=[block,...(childrenByParent.get(selectedBlock)||[])], visible=all.filter(matchNode);
      $('#appView').innerHTML=`<div class="view-header"><div><button class="btn" id="backOverview" type="button">← ${esc(t('all_blocks'))}</button><h1>${esc(block.id)} · ${esc(tc(block.title))}</h1><p>${esc(tc((block.operational_fields||{})['Зачем']||''))}</p></div><div class="view-actions"><button class="btn primary" id="reviewBlockNext" type="button">${esc(t('next_node'))}</button></div></div>${metricsHtml()}${visible.length?`<section class="panel"><div class="panel-title"><h2>${esc(t('block_graph'))}</h2><div class="legend"><span><i class="dot" style="background:var(--blue)"></i>${esc(t('step'))}</span><span><i class="dot" style="background:var(--green)"></i>${esc(t('artifact'))}</span><span><i class="dot" style="background:var(--amber)"></i>gate</span><span><i class="dot" style="background:var(--red)"></i>${esc(t('failure'))}</span></div></div><div class="graph-wrap"><div class="graph-controls"><button id="zoomIn" type="button" aria-label="${esc(t('zoom_in'))}">+</button><button id="zoomOut" type="button" aria-label="${esc(t('zoom_out'))}">−</button><button id="zoomFit" type="button" aria-label="${esc(t('fit'))}">⌂</button></div><svg id="blockGraph" role="img" aria-label="${esc(t('block_graph'))}: ${esc(tc(block.title))}"></svg></div><div id="nodeList" class="node-list"></div></section>`:`<div class="empty-state">${esc(t('no_results'))}</div>`}`;
      $('#backOverview').addEventListener('click',renderOverview); $('#reviewBlockNext').addEventListener('click',()=>nextReview(selectedBlock));
      if(visible.length){ renderSvg(visible); renderNodeList(visible); }
    }
    function renderNodeList(list){
      $('#nodeList').innerHTML=list.map(n=>{const a=annotation(n.id);return `<button class="node-row ${selectedNode===n.id?'selected':''}" data-node="${esc(n.id)}" type="button"><i class="type-icon ${esc(n.type)}"></i><span><strong>${esc(n.id)}</strong><br><small>${esc(tc(n.title))}</small></span><span class="badge ${needsAttention(a)?'attention':''}">${esc(statusLabels[a.status]||a.status)}</span></button>`}).join('');
      $$('.node-row').forEach(btn=>btn.addEventListener('click',()=>selectNode(btn.dataset.node)));
    }
    let svgView=null;
    function renderSvg(list){
      const svg=$('#blockGraph'), ids=new Set(list.map(n=>n.id));
      const groups={step:[],artifact:[],gate:[],failure:[],other:[]};
      list.forEach(n=>{ if(n.type==='step'||n.type==='block')groups.step.push(n);else if(n.type==='artifact')groups.artifact.push(n);else if(n.type==='gate'||n.type==='decision')groups.gate.push(n);else if(n.type==='failure')groups.failure.push(n);else groups.other.push(n); });
      const columns=[groups.step,groups.artifact,groups.gate,[...groups.failure,...groups.other]], positions=new Map(); let maxRows=1;
      columns.forEach((col,ci)=>{maxRows=Math.max(maxRows,col.length);col.forEach((n,ri)=>positions.set(n.id,{x:35+ci*245,y:35+ri*92}));});
      const width=35+columns.length*245, height=Math.max(430,55+maxRows*92);
      const allowed=new Set(['on_success','on_failure','returns_to','unblocks','conditionally_unblocks','produces','accepted_by']);
      const edges=(graph.edges||[]).filter(e=>ids.has(e.source)&&ids.has(e.target)&&allowed.has(e.relation));
      const lines=edges.map(e=>{const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)return'';const cls=e.relation.includes('failure')||e.relation==='returns_to'?'failure':e.relation.includes('success')||e.relation.includes('unblocks')?'success':e.relation==='produces'?'produces':'';return `<path class="edge ${cls}" d="M ${a.x+184} ${a.y+28} C ${a.x+215} ${a.y+28}, ${b.x-30} ${b.y+28}, ${b.x} ${b.y+28}" marker-end="url(#arrow)"/>`}).join('');
      const boxes=list.map(n=>{const p=positions.get(n.id),a=annotation(n.id),title=String(tc(n.title)||'');return `<g class="node ${esc(n.type)} ${selectedNode===n.id?'selected':''} ${hasText(a)||a.status!=='unreviewed'?'has-review':''}" data-node="${esc(n.id)}" transform="translate(${p.x} ${p.y})" tabindex="0" role="button"><rect width="184" height="56"></rect><text class="node-id" x="10" y="16">${esc(n.id)} · ${esc(typeLabels[n.type]||n.type)}</text><text x="10" y="35">${esc(title.slice(0,25))}${title.length>25?'…':''}</text></g>`}).join('');
      svg.innerHTML=`<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6d83a6"></path></marker></defs>${lines}${boxes}`;
      svgView={x:0,y:0,w:width,h:height,baseW:width,baseH:height};applyView();
      $$('.node',svg).forEach(el=>{el.addEventListener('click',()=>selectNode(el.dataset.node));el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectNode(el.dataset.node)}})});
      $('#zoomIn').addEventListener('click',()=>zoom(.82));$('#zoomOut').addEventListener('click',()=>zoom(1.22));$('#zoomFit').addEventListener('click',()=>{svgView={x:0,y:0,w:width,h:height,baseW:width,baseH:height};applyView()});
      svg.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY>0?1.1:.9)},{passive:false});
    }
    function zoom(f){if(!svgView)return;const nw=Math.max(350,Math.min(svgView.baseW*3,svgView.w*f)),nh=svgView.h*(nw/svgView.w);svgView.x+=(svgView.w-nw)/2;svgView.y+=(svgView.h-nh)/2;svgView.w=nw;svgView.h=nh;applyView()}
    function applyView(){if(svgView)$('#blockGraph').setAttribute('viewBox',`${svgView.x} ${svgView.y} ${svgView.w} ${svgView.h}`)}
    function selectNode(id){ selectedNode=id; renderInspector(); if(viewMode==='block'){ $$('.node,.node-row').forEach(el=>el.classList.toggle('selected',el.dataset.node===id)); } if(innerWidth<=820)$('#inspector').classList.add('mobile-open'); }
    function detailsFor(n){
      const pairs=[]; Object.entries(n.operational_fields||{}).forEach(([k,v])=>pairs.push([k,v]));
      Object.entries(n.artifact_contract||{}).forEach(([k,v])=>pairs.push([k,v]));
      if(n.implements?.length)pairs.push([t('implements'),n.implements.join(', ')]); if(n.implementation_evidence?.length)pairs.push(['Evidence',n.implementation_evidence.join('\n')]);
      return pairs.length?`<details class="details" open><summary>${esc(t('node_contract'))}</summary><dl>${pairs.map(([k,v])=>`<dt>${esc(tc(k))}</dt><dd>${esc(tc(v))}</dd>`).join('')}</dl></details>`:'';
    }
    function renderInspector(){
      const n=nodeById.get(selectedNode); if(!n){$('#inspector').innerHTML=`<div class="inspector-empty">${esc(t('select_node'))}</div>`;return}
      const a=annotation(n.id), names=review.reviewer_names;
      $('#inspector').innerHTML=`<button class="btn" id="closeInspector" type="button" style="float:right">×</button><span class="block-id">${esc(n.id)}</span><h2>${esc(tc(n.title))}</h2><div class="node-meta"><span class="pill">${esc(typeLabels[n.type]||n.type)}</span><span class="pill">${esc(implLabels[n.implementation_status]||n.implementation_status)}</span><span class="pill">${esc((n.implements||[]).join(', ')||t('no_trace'))}</span></div>${detailsFor(n)}<div class="status-row"><select id="nodeReviewStatus" aria-label="${esc(t('review_status'))}">${Object.entries(statusLabels).map(([v,l])=>`<option value="${v}" ${a.status===v?'selected':''}>${esc(l)}</option>`).join('')}</select><button class="btn" id="copyDiscussion" type="button">${esc(t('copy'))}</button></div><div class="fields">
        ${field('owner_observation',t('owner_observation'),a.owner_observation,'owner')}
        ${field('owner_question',t('owner_question'),a.owner_question,'owner')}
        ${field('owner_proposal',t('owner_proposal'),a.owner_proposal,'owner')}
        ${field('reviewer_1',names.reviewer_1||t('reviewer_1'),a.reviewer_1,'review')}
        ${field('reviewer_2',names.reviewer_2||t('reviewer_2'),a.reviewer_2,'review')}
      </div>`;
      $('#closeInspector').addEventListener('click',()=>$('#inspector').classList.remove('mobile-open'));
      $('#nodeReviewStatus').addEventListener('change',e=>{annotation(n.id,true).status=e.target.value;touch(n.id)});
      $$('textarea[data-field]',$('#inspector')).forEach(el=>el.addEventListener('input',e=>{annotation(n.id,true)[e.target.dataset.field]=e.target.value;touch(n.id)}));
      $('#copyDiscussion').addEventListener('click',()=>copyDiscussion(n,a));
    }
    function field(key,label,value,cls){return `<div class="field ${cls}"><label for="field_${key}">${esc(label)}</label><textarea id="field_${key}" data-field="${key}" placeholder="${esc(t('empty_comment'))}">${esc(value)}</textarea></div>`}
    async function copyDiscussion(n,a){
      const names=review.reviewer_names, text=[`${n.id} — ${tc(n.title)}`,`${t('node_type')}: ${typeLabels[n.type]||n.type}`,`${t('review_status')}: ${statusLabels[a.status]||a.status}`,``,`${names.owner} · ${t('owner_observation')}:`,a.owner_observation||'—',``,`${names.owner} · ${t('owner_question')}:`,a.owner_question||'—',``,`${names.owner} · ${t('owner_proposal')}:`,a.owner_proposal||'—',``,`${names.reviewer_1}:`,a.reviewer_1||'—',``,`${names.reviewer_2}:`,a.reviewer_2||'—'].join('\n');
      try{await navigator.clipboard.writeText(text);toast(m('copied'))}catch(_){toast(m('clipboard_error'))}
    }
    function nextReview(blockId=null){
      const scope=blockId?[nodeById.get(blockId),...(childrenByParent.get(blockId)||[])]:nodes;
      const candidate=scope.filter(Boolean).find(n=>annotation(n.id).status!=='closed'&&!hasText(annotation(n.id))) || scope.filter(Boolean).find(n=>annotation(n.id).status!=='closed');
      if(!candidate){toast(m('scope_closed'));return}
      if(candidate.parent_id&&candidate.parent_id!==selectedBlock)openBlock(candidate.parent_id); else if(candidate.type==='block'&&candidate.id!==selectedBlock)openBlock(candidate.id); selectNode(candidate.id);
    }
    function exportReview(){ saveLocal(); download(`TASK-PLAN-PRO-review-${graph.graph_version}.json`,JSON.stringify(review,null,2),'application/json;charset=utf-8');toast(m('json_exported')); }
    function saveHtml(){
      saveLocal(); $('#review-data').textContent=JSON.stringify(review).replace(/<\//g,'<\\/');
      const output='<!doctype html>\n'+document.documentElement.outerHTML;
      download(`TASK-PLAN-PRO-OPERATIONAL-REVIEW-${graph.graph_version}.html`,output,'text/html;charset=utf-8');toast(m('html_saved'));
    }
    function importReview(file){
      $('#importButton').disabled=true;$('#importButton').dataset.state='submitting';
      const finishImport=()=>{$('#importButton').disabled=false;delete $('#importButton').dataset.state};
      const reader=new FileReader(); reader.onload=()=>{try{const incoming=JSON.parse(reader.result);if(incoming.graph_id!==graph.graph_id)throw new Error(m('wrong_graph'));if(incoming.graph_sha256!==embeddedReview.graph_sha256&&!confirm(m('different_graph')))return;
        if(!incoming.reviewer_names||typeof incoming.reviewer_names!=='object'||!incoming.annotations||typeof incoming.annotations!=='object'||Array.isArray(incoming.annotations))throw new Error('invalid review state');
        Object.entries(incoming.annotations).forEach(([id,value])=>{if(typeof id!=='string'||!value||typeof value!=='object'||Array.isArray(value)||!reviewStatuses.has(value.status||'unreviewed')||reviewFields.some(field=>typeof (value[field]??'')!=='string'))throw new Error(`invalid annotation: ${id}`)});
        review.reviewer_names={...review.reviewer_names,...(incoming.reviewer_names||{})};
        Object.entries(incoming.annotations||{}).forEach(([id,val])=>{const existing=review.annotations[id]||{};review.annotations[id]={...existing,...val};});
        review.updated_at=new Date().toISOString();localStorage.setItem(storageKey,JSON.stringify(review));renderNav();viewMode==='overview'?renderOverview():renderBlock();if(selectedNode)renderInspector();toast(m('imported'));
      }catch(e){toast(`${m('import_failed')}: ${e.message}`)}finally{finishImport()}}; reader.onerror=()=>{finishImport();toast(m('read_failed'))};reader.readAsText(file);
    }
    function init(){
      $('#languageSelect').innerHTML=(contentCatalog.locales||[contentCatalog.source_locale||'en']).map(code=>`<option value="${esc(code)}">${esc(code.toUpperCase())}</option>`).join('');
      $('#versionLine').textContent=`${graph.graph_version} · ${nodes.length} ${m('nodes')} · ${blocks.length} ${m('blocks')}`;
      applyStaticI18n();renderNav();renderOverview();
      $('#overviewButton').addEventListener('click',renderOverview);$('#nextButton').addEventListener('click',()=>nextReview());
      $('#languageSelect').addEventListener('change',e=>changeLocale(e.target.value));
      ['typeFilter','implementationFilter','reviewFilter'].forEach(id=>$('#'+id).addEventListener('change',()=>viewMode==='overview'?renderOverview():renderBlock()));
      $('#searchInput').addEventListener('input',()=>viewMode==='overview'?renderOverview():renderBlock());
      $('#exportButton').addEventListener('click',exportReview);$('#saveHtmlButton').addEventListener('click',saveHtml);
      $('#importButton').addEventListener('click',()=>$('#importFile').click());$('#importFile').addEventListener('change',e=>{if(e.target.files[0])importReview(e.target.files[0]);e.target.value=''});
      $('#reviewer1Name').value=review.reviewer_names.reviewer_1||HELP[locale].reviewer1;$('#reviewer2Name').value=review.reviewer_names.reviewer_2||HELP[locale].reviewer2;
      ['reviewer1Name','reviewer2Name'].forEach((id,index)=>$('#'+id).addEventListener('input',e=>{review.reviewer_names[index?'reviewer_2':'reviewer_1']=e.target.value;review.updated_at=new Date().toISOString();dirty=true;clearTimeout(saveTimer);saveTimer=setTimeout(saveLocal,350);if(selectedNode)renderInspector()}));
      $('#helpButton').addEventListener('click',()=>$('#helpModal').classList.add('open'));$('#closeHelp').addEventListener('click',()=>$('#helpModal').classList.remove('open'));$('#helpModal').addEventListener('click',e=>{if(e.target.id==='helpModal')e.currentTarget.classList.remove('open')});
      document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){e.preventDefault();$('#searchInput').focus()}if(e.key==='Escape'){$('#helpModal').classList.remove('open');$('#inspector').classList.remove('mobile-open')}});
      window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue=''}});
    }
    try{init()}catch(error){console.error(error);$('#appView').innerHTML=`<div class="error-state"><h1>${esc(m('open_failed'))}</h1><p>${esc(error.message)}</p><p>${esc(m('integrity'))}</p></div>`}
  })();
  </script>
</body>
</html>
'''


if __name__ == "__main__":
    main()
