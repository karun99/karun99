# Security Policy

## Supported Versions

Only the latest release of this project is actively supported with security updates. Older versions may receive security fixes on a best-effort basis.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| < latest | :x:                |

## Incident Response Mechanism (Dependabot)

This repository uses **Dependabot** to monitor dependencies, raise security alerts, and open version-update PRs. The following incident-response process applies to every Dependabot alert.

### 1. Triage & Severity Classification

| Severity  | CVSS Range | Example                    |
| --------- | ---------- | -------------------------- |
| Critical  | 9.0–10.0   | RCE, auth bypass           |
| High      | 7.0–8.9    | SQLi, XSS, SSRF            |
| Medium    | 4.0–6.9    | DoS, info disclosure       |
| Low       | 0.1–3.9    | Linting, best-practice     |

Every new alert is triaged within **24 hours**. Alerts are confirmed, reproduced, or dismissed with justification in the Dependabot dashboard.

### 2. Remediation SLA

| Severity  | Remediation SLA    | Action                                                                |
| --------- | ------------------ | --------------------------------------------------------------------- |
| Critical  | 48 hours           | Patch immediately, pin exact fixed version, release hotfix, redeploy  |
| High      | 7 days             | Patch in next release, no workaround required to be documented        |
| Medium    | 30 days            | Patch in next scheduled release                                       |
| Low       | 90 days            | Schedule with regular maintenance                                     |

### 3. Dependabot Version-Updates Workflow

1. Dependabot opens a PR for the vulnerable dependency.
2. CI runs the test suite against the updated dependency — the PR must pass all checks.
3. A maintainer reviews the diff (changelog, breaking changes, licenses).
4. Merged PRs are deployed per the documented release process.
5. The alert is automatically closed once the fixed version is merged.

### 4. Escalation & Contact

- **Security contact:** `karun99` via GitHub.
- **Critical incidents:** open an advisory or contact maintainers immediately; do not wait for the weekly review.
- **Downtime / exploit in the wild:** immediate hotfix branch + backport to supported releases.

### 5. Public Disclosure

- Patches are released **before** public disclosure.
- Advisory details are published through GitHub Security Advisories and/or OsVDB-compatible channels after the fix is deployed.
- 90 days of responsible disclosure applies for third-party reports (Coordinated Disclosure).

### 6. Post-Incident Review

After every Critical/High incident a post-mortem is written covering:
- Root cause and affected dependency versions
- Detection and response timeline (when alert opened → patched → deployed)
- Preventive measures (dependency pinning, CI gates, runtime monitoring)
- Lessons learned and process changes

## Reporting a Vulnerability

Use the GitHub private security advisory feature:

1. Open the **Security** tab of this repository.
2. Click **Report a vulnerability**.
3. Provide a description, affected dependency/version, and proof-of-concept if available.
4. Expected acknowledgment: within **3 business days**.

You will receive a response with next steps and a timeline. Please do **not** disclose the issue publicly until it has been addressed.

## Disclosure Policy

- Reports are kept confidential and only shared with maintainers.
- Credit is given to reporters in release notes/advisories unless anonymity is requested.
- Malware, abuse, or spam reports are outside the scope of this policy.

## Dependency Hygiene

- Direct dependencies are pinned or semver-locked in manifests (`package.json`, `requirements.txt`, `pyproject.toml`, etc.).
- Lockfiles are kept in-repo for reproducible builds.
- PRs that introduce known-vulnerable packages are blocked by Dependabot and CI.
- Deprecated or unmaintained packages are migrated at least twice a year.