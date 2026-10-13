# 🌱 BIO-AUDIT.md — Bio-Inspired Autonomous Audit Configuration

Owner: karun99
Derived from: Bio-Inspired Security Policy v1.0 + SECURITY.md (Dependabot Incident Response)
Guardrails: Jataka · Soul · Sahaja · Dunce
Status: Active
Review cycle: Annual + post-incident

---

## 📋 0. Metadata

```yaml
config_name: bio-inspired-autonomous-audit
version: 1.1.0
owner: karun99
supported_versions:
  latest: supported
  older: best_effort
slas:
  critical: 48h
  high: 7d
  medium: 30d
  low: 90d
triage_window: 24h
disclosure_window: 90d
human_override: always_allowed
code_audit:
  enabled: true
  engines: [codeql, dependency-review, sarif-upload]
  fail_on: [critical, high]
```

---

## 🧬 1. Core Mapping — Policy → Component

| Bio Principle | Component | Function | Dependabot Role |
| ------------- | --------- | -------- | --------------- |
| Immune memory | Jataka | Causal precedent + priority | Blocks regressions of past CVEs; ranks by severity |
| Neural + self-healing | Soul | Intent continuity | Enforces SECURITY.md invariants |
| Ecological balance | Sahaja | Minimal-force fix | Picks smallest reversible patch |
| Apoptosis | Dunce | Circuit breaker | Quarantines + lessons-learned |

---

## 🛡️ 2. Jataka Guardrails — Causal Precedent & Priority

Jataka remembers past incidents and uses them to both **gate** and **prioritise** every
incoming Dependabot update. Every alert is assigned a single priority (`P0`–`P3`); the
priority is the **strongest** match across the trigger rules below (first match wins,
`P0` is strongest).

```yaml
jataka:
  version: 1.1
  precedent_sources:
    - security_incidents.db
    - dependabot_alert_history
    - pr_rejections.log
    - nvd.cve.feed
    - osvdb.feed
    - cisa_kev.feed
  priority_labels:
    - prio/P0
    - prio/P1
    - prio/P2
    - prio/P3
  priority_model:
    - id: P0
      name: Karmic Emergency
      tier: critical
      sla: 48h
      labels: [prio/P0, security, jataka]
      triggers:
        - cisa_kev_match: true
        - exploit_in_the_wild: true
        - cvss_score_gte: 9.0
      action: block_and_notify_then_hotfix
    - id: P1
      name: Precedent Harm
      tier: high
      sla: 7d
      triggers:
        - cvss_score_gte: 7.0
        - reintroduces_remediated_cve: true
        - similarity_gte: 0.85
      action: hold_two_clean_cycles
    - id: P2
      name: Renewal
      tier: medium
      triggers:
        - cvss_score_gte: 4.0
      sla: 30d
      action: quarantine_on_ambiguity
    - id: P3
      name: Maintenance
      tier: low
      triggers:
        - cvss_score_gte: 0.1
        - no_known_cve: true
      sla: 90d
      action: schedule
  rules:
    - id: JAT-001
      name: Karmic Regression Check
      description: Reject if update reintroduces a previously remediated CVE
      priority: P1
      action: block_and_notify
    - id: JAT-002
      name: Precedent Harm Scan
      description: Similarity match vs past failed auto-fixes
      threshold: 0.85
      priority: P1
      action: quarantine
    - id: JAT-003
      name: Silent Sage Rule
      description: Critical-path packages require two clean cycles before autonomy
      action: hold
      priority: P1
    - id: JAT-004
      name: Disclosure Window Guard
      description: Never merge before 90-day coordinated disclosure if third-party report
      action: block
      priority: P0
```

**Priority resolution** (implemented by `scripts/jataka_query.py`):

1. Severity baseline from CVSS — `≥9.0 → P0`, `7.0–8.9 → P1`, `4.0–6.9 → P2`, `<4.0 → P3`.
2. Escalate on guardrail match — `JAT-001`/`JAT-002`/`JAT-003` → at least `P1`, `JAT-004` → `P0`.
3. Escalate on threat intel — CISA KEV or exploit-in-the-wild → `P0`.
4. Result = strongest of (1)(2)(3). The chosen label `prio/Px` is applied to the PR.

---

## 🧠 3. Soul — Intent Continuity

```yaml
soul:
  version: 1.0
  source_of_truth: SECURITY.md
  invariants:
    supported_versions_only: [latest]
    license_allowlist: [MIT, Apache-2.0, BSD-3-Clause, MPL-2.0, ISC]
    forbidden_licenses: [GPL-3.0, AGPL-3.0, SSPL, BUSL-1.1]
    lockfiles_required: true
    pinned_direct_deps: true
    intent_file: .soul/intent.md
    baseline: .soul/baseline.json
  drift_checks:
    - id: SOUL-001
      name: License Continuity
      fail_action: reject_and_log
    - id: SOUL-002
      name: Maintainer Intent Alignment
      method: semantic_diff_vs_intent_md
      threshold: 0.70
      fail_action: escalate_to_karun99
    - id: SOUL-003
      name: Posture Non-Regression
      rule: no_new_high_or_critical
      fail_action: block
    - id: SOUL-004
      name: Lockfile Fidelity
      rule: lockfile_must_match_manifest
      fail_action: block
    - id: SOUL-005
      name: Deprecation Watch
      rule: flag_unmaintained_packages
      cadence: twice_per_year
      fail_action: open_migration_issue
```

### .soul/intent.md (project-specific)

```markdown
# Project Soul — karun99's Repository

## Identity
- Mission: ship secure, reproducible releases on `latest` only.
- Maintainer hours: 09:00–22:00 IST.
- Contact: @karun99

## Invariants
- Security-first; never break API compatibility for minor CVEs.
- Prefer upstream patches over forks.
- All autonomous merges reversible within 24h.
- No auto-merge on critical-path after 22:00 IST.
- Lockfiles always in-repo.

## Forbidden Drifts
- New GPL/AGPL/SSPL/BUSL dependencies.
- Adding transitive deps without review.
- Modifying CI/CD security gates.
- Skipping the 90-day disclosure window.
```

---

## 🌊 4. Sahaja — Minimal Force

```yaml
sahaja:
  version: 1.0
  preference_order:
    - native_dependabot_update
    - upstream_security_patch
    - pinned_version_bump
    - fork_with_backport
  constraints:
    max_diff_lines: 200
    max_files_touched: 10
    no_new_dependencies: true
    revert_window_hours: 24
    hotfix_branch_prefix: "hotfix/"
  slas:
    critical: 48h
    high: 7d
    medium: 30d
    low: 90d
  checks:
    - id: SAH-001
      name: Effort Budget
      reject_if: exceeds_constraints
    - id: SAH-002
      name: Native Path First
      reject_if: fork_while_native_available
    - id: SAH-003
      name: Reversibility
      require: rollback_plan_attached
    - id: SAH-004
      name: SLA Clock
      reject_if: proposed_merge_exceeds_sla
```

---

## 🔥 5. Dunce — Circuit Breaker

```yaml
dunce:
  version: 1.0
  triggers:
    - id: DUN-001
      name: Confidence Floor
      condition: confidence < 0.75
      action: halt_and_label("dunce:low-confidence")
    - id: DUN-002
      name: Contradiction Alert
      condition: verdicts_disagree
      action: quarantine_and_escalate_to_karun99
    - id: DUN-003
      name: Post-Merge Regression
      condition: new_alert_within_24h
      action: revert + incident + reopen_alert
    - id: DUN-004
      name: Rate Ceiling
      condition: merges_per_hour > 5
      action: freeze_6h
    - id: DUN-005
      name: SLA Breach
      condition: alert_age > sla
      action: escalate_critical_channel
    - id: DUN-006
      name: Exploit-In-The-Wild
      condition: cisa_kev_match == true
      action: immediate_hotfix + backport + notify
  post_mortem:
    required_for: [Critical, High]
    template: .dunce/lessons/{timestamp}.md
    contents:
      - root_cause
      - affected_versions
      - detection_and_response_timeline
      - preventive_measures
      - lessons_learned
    notify: [karun99]
    feeds_into: jataka
```

---

## 🔄 6. Unified Pipeline

```
Dependabot Alert
      │
      ▼
 ┌──────────┐  assign priority (P0–P3) ┌────────┐
 │ Jataka   ├─────────────────────────►│ label  │
 └────┬─────┘          fail            └────┬───┘
      │ pass                               │
      ▼                                    ▼
 ┌──────────┐  fail   ┌────────┐
 │  Soul    ├────────►│ Dunce  │──► Quarantine + Lessons
 └────┬─────┘         └────────┘
      │ pass
      ▼
 ┌──────────┐  fail   ┌────────┐
 │ Sahaja   ├────────►│ Dunce  │
 └────┬─────┘         └────────┘
      │ pass
      ▼
 Auto-PR → Code Audit (CodeQL + dependency-review) → CI → Merge → 24h Watchdog → Advisory
```

---

## 🔍 7. Code Audit (SARIF + CodeQL)

```yaml
code_audit:
  version: 1.0
  engines:
    codeql:
      languages: [python, javascript-typescript]
      queries: security-extended
      upload_sarif: true
    dependency_review:
      fail_on_severity: high
      allow_licenses: [MIT, Apache-2.0, BSD-3-Clause, MPL-2.0, ISC]
      deny_licenses: [GPL-3.0, AGPL-3.0, SSPL, BUSL-1.1]
    sarif:
      upload_to: github-security-tab
  gate:
    fail_if_new: [critical, high]
```

Every finding is uploaded to the GitHub Security tab as SARIF. Critically, the code-audit
job runs on `pull_request` (read-only token + `security-events: write`) and **never**
checks out untrusted code under `pull_request_target`.

---

## ⚙️ 8. GitHub Actions Workflow

Save as `.github/workflows/bio_audit_autofix.yml`

```yaml
name: Bio-Inspired Autonomous Audit

on:
  schedule: [{cron: "0 */6 * * *"}]
  workflow_dispatch:
  pull_request:
    types: [opened, synchronize, reopened]
  pull_request_target:
    types: [opened, synchronize]

permissions:                 # complete permission set required by the audit + autofix
  actions: read
  checks: write
  contents: write
  issues: write
  metadata: read
  packages: read
  pull-requests: write
  security-events: write
  statuses: write

jobs:
  code_audit:
    if: github.event_name != 'pull_request_target'
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: [python, javascript-typescript]
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
          queries: security-extended
      - uses: github/codeql-action/autobuild@v3
      - uses: github/codeql-action/analyze@v3

  dependency_review:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: high

  bio_audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Kill Switch Check
        id: killswitch
        run: |
          if [ -f .bio/automation_lock.json ]; then
            echo "locked=true" >> $GITHUB_OUTPUT
          else
            echo "locked=false" >> $GITHUB_OUTPUT
          fi

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: python -m pip install --disable-pip-version-check pyyaml

      - name: Jataka Precedent Query + Priority
        id: jataka
        if: steps.killswitch.outputs.locked == 'false'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python scripts/jataka_query.py

      - name: Soul Drift Check
        id: soul
        if: steps.killswitch.outputs.locked == 'false'
        run: python scripts/soul_check.py

      - name: Sahaja Effort Budget
        id: sahaja
        if: steps.killswitch.outputs.locked == 'false'
        run: python scripts/sahaja_budget.py

      - name: Dunce Consensus Gate
        id: dunce
        if: steps.killswitch.outputs.locked == 'false'
        run: python scripts/dunce_gate.py

      - name: Autonomous Merge
        if: steps.dunce.outputs.verdict == 'pass' && steps.jataka.outputs.priority != 'P0'
        run: gh pr merge --auto --squash "${{ github.event.pull_request.number }}"

      - name: Quarantine
        if: steps.dunce.outputs.verdict != 'pass' || steps.jataka.outputs.priority == 'P0'
        run: python scripts/dunce_quarantine.py

      - name: Lessons-Learned
        if: always()
        run: python scripts/dunce_postmortem.py
```

---

## 📊 9. Audit Rule Matrix (Policy → Control)

| SECURITY.md § | Principle | Jataka | Soul | Sahaja | Dunce |
| ------------- | --------- | :----: | :--: | :----: | :---: |
| Supported Versions | Latest only |  | ✔ | ✔ |  |
| Triage 24h | Immune detection | ✔ |  |  | ✔ |
| SLA 48h/7d/30d/90d | Ecological balance | ✔ |  | ✔ | ✔ |
| Dependabot Workflow | Swarm defense | ✔ |  | ✔ | ✔ |
| Escalation (karun99) | Neural alerting | ✔ | ✔ |  | ✔ |
| Public Disclosure (90d) | DNA integrity | ✔ | ✔ |  |  |
| Post-Incident Review | Self-healing | ✔ |  |  | ✔ |
| Code Audit (SARIF) | Immune surveillance | ✔ | ✔ |  | ✔ |

---

## 🧯 10. Kill Switch

```bash
if [ ! -d .bio ]; then mkdir -p .bio; fi
printf '{"locked": true, "reason": "human-override", "at": "%s"}\n' "$(date -u +%FT%TZ)" > .bio/automation_lock.json
```

Any maintainer can commit `.bio/automation_lock.json`. Dunce treats it as an absolute halt.

---

## 📁 11. Repository Layout

```
.
├── BIO_AUDIT.md
├── SECURITY.md
├── .github/
│   ├── workflows/
│   │   └── bio_audit_autofix.yml
│   ├── dependabot.yml
│   └── SECURITY_ADVISORY_TEMPLATE.md
├── .bio/
│   ├── automation_lock.json
│   └── config.yaml
├── .soul/
│   ├── intent.md
│   └── baseline.json
├── .dunce/
│   └── lessons/
├── scripts/
│   ├── _bio.py
│   ├── jataka_query.py
│   ├── soul_check.py
│   ├── sahaja_budget.py
│   ├── dunce_gate.py
│   ├── dunce_quarantine.py
│   └── dunce_postmortem.py
└── audit/
    ├── security_incidents.db
    ├── dependabot_alert_history
    ├── pr_rejections.log
    └── policy_audits.db
```

---

## 🔧 12. .github/dependabot.yml (Reference)

```yaml
version: 2
updates:
  - package-ecosystem: "npm"          # adjust per stack
    directory: "/"
    schedule: {interval: "daily"}
    open-pull-requests-limit: 5
    labels: ["dependencies", "security", "prio/P2"]
    commit-message:
      prefix: "chore(deps)"
      prefix-development: "chore(dev-deps)"
    groups:
      security:
        applies-to: security-updates
        patterns: ["*"]
    ignore:
      - dependency-name: "*"
        update-types: ["version-update:semver-major"]
```

> Dependabot cannot compute severity at PR-open time, so the config seeds a default
> `prio/P2` label; `scripts/jataka_query.py` then **upgrades** it to `prio/P0`–`prio/P3`
> from CVSS, precedent, and CISA KEV once the alert is live.

---

## ✅ 13. Activation Checklist

- [ ] Commit BIO_AUDIT.md to repo root
- [ ] Verify SECURITY.md exists and links here
- [ ] Add .github/workflows/bio_audit_autofix.yml
- [ ] Add .github/dependabot.yml
- [ ] Create .soul/intent.md (template in §3)
- [ ] Populate .soul/baseline.json (current SBOM + posture)
- [ ] Add Python scripts under /scripts
- [ ] Enable Dependabot alerts + security updates
- [ ] Enable CodeQL + dependency-review (requires GHAS or public repo)
- [ ] Enable branch protection: auto-merge only when dunce job passes
- [ ] Verify maintainer contact karun99 in Dunce notify list
- [ ] Test kill switch: commit .bio/automation_lock.json, confirm pipeline halts
- [ ] Dry-run one Dependabot PR through the full gate
- [ ] Confirm 90-day disclosure logic blocks premature merges

---

## 🧭 14. Policy Statement

Bio-inspired security principles guide adaptive, resilient, and accountable defenses.
Jataka remembers. Soul preserves. Sahaja minimizes. Dunce protects the whole by halting the part.

Supported versions: latest only (older = best-effort).
Triage: 24h · SLA: 48h / 7d / 30d / 90d · Disclosure: 90 days · Contact: karun99.

Biological analogies inform the framework; every control is validated with measurable evidence.

---

## 📌 Maintainer Notes

- Single file — everything lives in BIO_AUDIT.md.
- To change behavior: edit YAML blocks; scripts read from this file.
- To pause automation: commit .bio/automation_lock.json.
- Priorities are assigned by `scripts/jataka_query.py` (`prio/P0`–`prio/P3`).
