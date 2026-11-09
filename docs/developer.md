# Developer guide

## Architecture

The project metadata describes its public functions, interfaces, quality tools,
and collaboration policy. Keep implementation code and tests in clearly owned
locations, and keep public files synchronized with that metadata.

## Development setup

```bash
poetry install --all-extras
```

## Local checks

| Check | Command |
| --- | --- |
| Format | `poetry run ruff format --check .` |
| Lint | `poetry run ruff check .` |
| Type check | `poetry run mypy src` |
| Tests | `poetry run python -m pytest` |

See `CONTRIBUTING.md` in the repository root for the complete contribution policy.

## Function metadata

The public function descriptions in [Functions and operations](functions.md) should stay aligned with the implemented commands, accepted inputs, emitted outputs, and README `biotools-function` metadata blocks.

## Interface contracts

Keep public interface descriptions aligned with implementation files, documentation, and stability status.

- Command-line tool (Stable)
- Library (Stable)

## Project architecture

The Python package uses a `src` layout.
Runtime dependencies point inward: public entry points delegate reusable
behavior to the service layer.

```text
public entry points
    -> adapters/
    -> services/
```

Services must not import interface adapters.

Component paths:
- `src/maturity_meter/services/`
- `src/maturity_meter/adapters/`
- `tests/`

### Command-line tool

See the component paths above.

### Web API

See the component paths above.

## Automation

- `containers.yml`
- `docs.yml`
- `metadata.yml`
- `quality.yml`
- `tests.yml`

## Documentation publishing

The documentation workflow builds on pushes and pull requests, and deploys to GitHub Pages only from the default branch. In repository Settings → Pages, select **GitHub Actions** as the build source before the first deployment. Repositories created directly through RS Tools configure this automatically when GitHub Pages is available for the account.
