# Changelog

## 0.2.0 — unreleased

### Added
- `agenticwebqa-run-test` console script — runs a registered test from any
  project's `tests_registry.json`. Replaces `python docker/run_test.py`, which
  remains as a thin shim.
- `agenticwebqa-init` console script — bootstraps `tests_registry.json` and an
  empty `Models/` directory in the current project so first-time users have the
  scaffolding the engine and skills expect.
- Plugin `qa-ci-setup` skill — generates a CI workflow (GitHub Actions, GitLab,
  Jenkins, CircleCI) that runs the registered tests and opens a draft PR when
  selector drift causes a model to be re-learned.
- PyPI publish workflow (`.github/workflows/publish.yml`) using trusted
  publishing — `git tag v0.2.0 && git push --tags` triggers a release.

### Changed
- `run_test.py` moved from `docker/` into the `agenticwebqa` package so the CI
  workflow the `qa-ci-setup` skill generates works against an installed package
  rather than a repo-relative path.

## 0.1.0

Initial scaffold.
