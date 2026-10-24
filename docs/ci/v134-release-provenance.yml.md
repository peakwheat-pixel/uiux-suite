# Phase C: GitHub Actions release provenance (prepared, execution DEFERRED)

> Status: **DEFERRED** — no push/trigger credential is available in this session.
> The workflow below is ready to produce an external, verifiable build provenance
> when run by a repository maintainer. It does **not** replace independent review:
> a successful CI build proves provenance, not reviewer independence.

```yaml
name: v1.3.4-release-provenance

on:
  workflow_dispatch:
    inputs:
      ref:
        description: "commit/tag to build"
        required: true
  push:
    tags:
      - "v1.3.4"

permissions:
  contents: read
  id-token: write  # for artifact attestation (optional)

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ inputs.ref || github.ref }}
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install deps
        run: |
          python -m pip install -r requirements.txt
      - name: Tests
        run: |
          $env:PYTHONPATH="runtime"; python -m pytest tests -q
      - name: Build package
        run: |
          $env:PYTHONPATH="runtime"; python scripts/build_release.py
      - name: Record evidence
        run: |
          $zip = Get-ChildItem dist/*.zip | Select-Object -First 1
          $sha = (Get-FileHash $zip.FullName -Algorithm SHA256).Hash.ToLower()
          @{
            repository = "${{ github.repository }}"
            workflow_run_id = "${{ github.run_id }}"
            commit = "${{ github.sha }}"
            package = $zip.Name
            package_sha256 = $sha
            generated_at = (Get-Date).ToUniversalTime().ToString("o")
          } | ConvertTo-Json | Set-Content dist/build-provenance.json
      - uses: actions/upload-artifact@v4
        with:
          name: uiux-suite-1.3.4
          path: |
            dist/*.zip
            dist/SHA256SUMS.txt
            dist/build-provenance.json
      - name: Attest build provenance
        uses: actions/attest-build-provenance@v1
        with:
          subject-path: "dist/*.zip"

# Self-check before trusting an external run:
# 1. gh attestation verify dist/uiux-suite-1.3.4-win64.zip --repo <owner>/<repo>
# 2. compare the reported package_sha256 with the local SHA256SUMS.txt
# 3. only then may external_system be recorded as trust_source for the *build*;
#    independent review still requires a separate reviewer attestation.
```

## Why deferred

- The local checkout has an `origin` URL but no credential/CI trigger permission
  is available to this session; `git ls-remote` was attempted and refused.
- Fabricating an Actions run id or hashing claim would be evidence forgery, which
  this release forbids.
- Consequence: the final verdict stays at `ISOLATED_SESSION / INDEPENDENCE_UNVERIFIED`;
  `INDEPENDENT_REVIEW_PASS` is **not** claimed.

## Resume condition

A maintainer with push rights runs `workflow_dispatch` on commit `d5fc588` (or the
`v1.3.4` tag), then records the run id + artifact digest in
`evidence/release/github-actions-provenance.json`; R7 can then be re-evaluated
with `trust_source=external_system` **for the build**, and a separate independent
reviewer can supply the review attestation.
