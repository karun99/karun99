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
