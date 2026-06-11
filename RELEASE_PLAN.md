# Release Plan

The mechanics of cutting a Pomodoro release. Tag-driven: pushing a
tag of the form `vX.Y.Z` to GitHub triggers the entire pipeline.

## Versioning

Pomodoro follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR** — incompatible CLI / config / SQLite-schema changes
  (e.g. removing a binding, renaming a config section, dropping a
  migration). Today this means: anything that breaks an existing
  `~/.config/pomodoro/config.toml` or `~/.local/share/pomodoro/library.db`.
- **MINOR** — new screens, new bindings, new config keys, new
  plugins, new ADR-worthy behaviour. Backwards-compatible reads of
  old config + DB.
- **PATCH** — bug fixes, doc fixes, dependency bumps with no
  user-visible change, internal refactors.

Pre-releases use the `vX.Y.Z-rcN`, `vX.Y.Z-betaN`, or `vX.Y.Z-alphaN`
form. PEP 440 normalises these on PyPI.

## The pipeline

```
git tag vX.Y.Z              ─┐
git push origin vX.Y.Z       │
                             ▼
            .github/workflows/release.yml triggers
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
     build job          publish-pypi         github-release
  (sanity-check       (OIDC trusted        (extract CHANGELOG
   tag ↔ version,      publishing —          section, attach
   build sdist +       no API token         dist/* to release)
   wheel, twine        in secrets)
   check, upload
   artifact)
```

The pipeline mirrors BookReader's. See
[`.github/workflows/release.yml`](.github/workflows/release.yml) for
the source of truth.

## Pre-flight checklist

Before tagging:

1. **`main` is green.** `test.yml` passing, `docs.yml` passing.
2. **CHANGELOG ready.** Move items from `[Unreleased]` into a new
   `[X.Y.Z] — YYYY-MM-DD` section. Keep the narrative intro short
   (1–3 sentences) and group entries under `Added` / `Changed` /
   `Fixed` / `Removed` / `Deprecated` / `Security`.
3. **Version bumped.** Edit `pyproject.toml` `version = "X.Y.Z"`.
   This must match the tag exactly — the build job will fail the
   release if they diverge.
4. **ROADMAP updated.** Move the just-shipped phase to `(done)` with
   a one-line summary; promote the next phase if it's now active.
5. **ADRs.** Any new architectural decisions in this release are
   recorded under `docs/adr/`.
6. **Smoke test locally.**
   ```bash
   pip install build twine
   python -m build
   twine check dist/*
   pipx install ./dist/pomodoro-X.Y.Z-py3-none-any.whl
   pomodoro                  # launches; press q
   ```

## Cutting the release

```bash
git checkout main
git pull --ff-only
git tag -a vX.Y.Z -m "release: vX.Y.Z"
git push origin vX.Y.Z
```

Watch `release.yml` in the Actions tab. The three jobs run
sequentially (`build` → `publish-pypi` → `github-release`).
Expected duration: ~3–4 minutes.

## Pre-releases

```bash
git tag -a v0.2.0-rc1 -m "release: v0.2.0-rc1"
git push origin v0.2.0-rc1
```

`release.yml` recognises the `-` suffix and marks the GitHub release
as **pre-release**; PyPI tags the upload with `0.2.0rc1` (PEP 440
normalisation). Users opt in with `pipx install --pre pomodoro` or
`pip install pomodoro==0.2.0rc1`.

## Rollback

Releases on PyPI are immutable — you cannot delete a published
version and re-upload the same number. To unship:

1. **Yank** on PyPI via `twine yank dist/pomodoro-X.Y.Z*` (or the
   PyPI web UI). Users with the version installed keep it; new
   installs skip it.
2. **Delete the GitHub release** (keeps the tag) and mark it
   pre-release if you prefer to keep it visible.
3. **Open a hotfix PR** that bumps to `vX.Y.(Z+1)`, fix the cause,
   then run the release again.

The tag itself should stay — deleting tags rewrites history and
breaks anyone who already pulled.

## Post-release

After the GitHub release is published:

1. Open a `chore: bump dev version` PR that bumps `pyproject.toml`
   to the next `X.Y.(Z+1)-dev` (or the next planned minor).
2. Add a new empty `[Unreleased]` section at the top of
   `CHANGELOG.md`.
3. Announce in the README's "Project background" section if the
   release is a milestone (a new minor or major).

## Trusted publishing setup (one-time)

Done out-of-band by the maintainer:

1. Create a PyPI account.
2. Bind the project to the GitHub OIDC publisher (PyPI →
   *Manage* → *Publishing* → *Add a new pending publisher*):
   - **Owner**: `prajwalmahajan101`
   - **Repository**: `pomban`
   - **Workflow filename**: `release.yml`
   - **Environment** (optional but recommended): `pypi`
3. Create a `pypi` environment in the GitHub repo settings with the
   single rule "deployment branches: tags matching `v*`".

No API tokens are stored anywhere. The OIDC handshake on every
release is the only authentication.
