# Copilot Instructions (Simulated City Workshop)

This repository is a beginner-friendly workshop template for learning agent-based programming in Python.

## Goals and scope

- Teachability first: simple, explicit control flow and readable code.
- Smallest change that satisfies the requirement; avoid extra features/tooling.
- Documentation-driven development: update docs before behavior changes.

## Architecture and key modules

- Library code lives in `src/simulated_city/` and intentionally ships only helpers, not a full simulation.
- Configuration is loaded via `simulated_city.config.load_config()`, which searches parent directories for `config.yaml` to support running from `notebooks/`.
- MQTT helpers are in `simulated_city.mqtt` with `connect_mqtt()` and `publish_json_checked()` (self-subscribe publish verifier).
- Optional geospatial helpers live in `simulated_city.geo` (pyproj-backed EPSG transforms).
- CLI smoke entry point is `python -m simulated_city` (see `src/simulated_city/__main__.py`).
- use anymap-ts for mapping and pypaho for MQTT client. Avoid extra dependencies to keep it simple.

## Configuration and secrets

- Non-secret defaults live in `config.yaml` (MQTT broker host, port, TLS, base topic).
- Secrets are loaded from `.env` (gitignored). MQTT credentials are resolved via env var names in `config.yaml`.

## Developer workflows

- Install: `pip install -e ".[dev,notebooks]"` (add `.[geo]` for CRS helpers).
- Tests: `python -m pytest` (see `tests/` for minimal sanity checks).
- Notebooks: `python -m jupyterlab`.

## Code conventions

- Prefer dataclasses for config containers (see `MqttConfig`, `AppConfig`).
- Public modules/functions/classes should have short, beginner-friendly docstrings.
- Comment the “why” for rules/assumptions in simulations; avoid obvious comments.

## Documentation-driven development

- Update `docs/` first: `docs/overview.md`, `docs/setup.md`, `docs/mqtt.md`, `docs/exercises.md` depending on the change.
- Then implement code updates and add or adjust a small test in `tests/` if relevant.

### PR requirement (always)

Include this line in PR descriptions:

```
Docs updated: yes/no
```

If yes, list doc paths (example: `docs/mqtt.md`). If no, add one sentence why not.

# Project documentation writing guidelines

## General Guidelines
- Write clear and concise documentation.
- Use consistent terminology and style.
- Include code examples where applicable.

## Grammar
* Use present tense verbs (is, open) instead of past tense (was, opened).
* Write factual statements and direct commands. Avoid hypotheticals like "could" or "would".
* Use active voice where the subject performs the action.
* Write in second person (you) to speak directly to readers.

## Markdown Guidelines
- Use headings to organize content.
- Use bullet points for lists.
- Include links to related resources.
- Use code blocks for code snippets.