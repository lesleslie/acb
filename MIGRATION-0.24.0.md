# Migration Guide for ACB 0.24.0

ACB 0.24.0 modernizes dependency management by replacing legacy
`[project.optional-dependencies]` extras with UV dependency groups and adds a few
related breaking changes. Follow the checklist below before upgrading.

## Key Changes

- **PEP 735 style dependency groups.** Install adapters and presets with
  `uv add --group <name>` instead of extras such as `uv add "acb[cache]"`.
- **No implicit adapters.** The core package now ships without optional adapters,
  so you must explicitly add the groups your application needs.
- **Updated APScheduler requirement.** Minimum supported version is now `>=4.0.0`.

## Upgrade Checklist

1. **Update installation scripts.**
   - Replace any extras based installs with dependency groups.
   - Example: `uv add "acb[cache,sql]"` → `uv add --group cache --group sql`.
1. **Pin new adapter groups where needed.**
   - Infrastructure: `cache`, `dns`, `ftpd`, `monitoring`, `requests`, `secret`,
     `smtp`, `storage`.
   - Data: `sql`, `nosql`, `vector`, `graph`.
   - AI/ML: `ai`, `embedding`, `reasoning`.
   - Support: `models`, `logger`, `mcp`, `demo`, `queue-apscheduler`.
   - Composite bundles: `minimal`, `api`, `microservice`, `webapp`,
     `webapp-plus`, `cloud-native`, `dataplatform`, `gcp`, `all`.
1. **Re-run deployment pipelines.**
   - Regenerate lock files with `uv lock --upgrade`.
   - Rebuild containers or serverless layers to ensure the new dependency layout
     is captured.
1. **Verify scheduler integrations.**
   - If you depend on APScheduler adapters, confirm compatibility with v4 APIs.
   - Update any import paths or configuration fields that changed upstream.

## Validation Steps

Run the standard quality workflow after migrating:

```bash
uv run ruff format
uv run ruff check
uv run pyright
uv run pytest --cov=acb --cov-fail-under=42
python -m crackerjack
```

Keep these commands (or their CI equivalents) in your release checklist to
ensure the dependency graph and adapters are wired correctly.
