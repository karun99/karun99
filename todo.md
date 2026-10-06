# TODO — Improvement Backlog

Audit date: 2026-10-01
Scope: `karun99` (profile + TRL tracker) and `karun99.github.io` (site)
Status: **verified, nothing fixed yet.** Every item below is evidence-backed.

---

## CRITICAL — TRL scores are wrong

### 1. `has_docker` is always `True` — every repo gets a fake Docker bonus

`tools/trl/trl_tracker.py:113`

```python
has_docker = any(f in lower or f.startswith(("dockerfile", "docker-compose", "compose.")) for f in ("dockerfile", "docker-compose.yml", "compose.yaml", "compose.yml"))
```

The comprehension iterates over four hardcoded *candidate names*, not over the repo's
file list. Two separate failures:

- `f in lower` is exact-membership against a list of **full paths** — `"dockerfile"` never
  equals `"subdir/Dockerfile"`, so it is never `True`.
- `f.startswith(("dockerfile", ...))` tests the *candidate name*, so it is `True` for all four
  iterations regardless of the repo.

Net effect: `has_docker == True` unconditionally, and `:164` awards `integ += 4` to every repo.
The README table confirms it — all 11 repos render the `🐳 Docker` chip uniformly.

**Verified:** run against `['readme.md','src/index.js','package.json']` → `True`.

- [x] Rewrite as `any(is_docker_path(f) for f in lower)` — done 2026-10-06, plus a regression test in `tools/trl/test_trl_signals.py`
- [x] Re-run the tracker and diff the score column — done 2026-10-06; 7 repos lost the fake Docker bonus, 4 gained real manifest/entry points, `teddy-techlearn` dropped a level
- [x] Check for level band changes — done; see the before/after in `TRL-ROADMAP.md`
- [x] Add a regression test — `tools/trl/test_trl_signals.py`, 15 cases pass

### 2. Subpath detection misses real manifests and entry points

`tools/trl/trl_tracker.py:104` and `:107` use the same `f in lower` exact-match bug.

- `has_manifest` misses `backend/pyproject.toml`, `frontend/package.json` → loses 6 code pts
- `has_entry` misses `pkg/main.go`, `src/main.py`, `lib/cli.ts` → loses 4 code pts

**Verified:** `['backend/pyproject.toml','frontend/package.json']` → `has_manifest == False`.

- [x] Match on `os.path.basename(f)` plus an explicit nested allowlist — done 2026-10-06 (`MANIFEST_FILES`, `is_manifest_path`)
- [x] For `has_entry`, also detect `cmd/`, `bin/`, `pkg/main.go`, `src/main.{py,go,rs}`, `app/` — done 2026-10-06 (`ENTRY_FILES` + `ENTRY_PREFIXES`)
- [x] Re-run and confirm code-maturity scores rise legitimately — done; `ai-content-studio` +10, `Collabuild`/`neural-harness`/`s-ai-soulbot` +4 each

### 3. Dead link: README points at a page that does not exist

`karun99` `README.md` — the new uncommitted MCP section links to
`https://karun99.github.io/mcp-servers.html` **twice** (the 🔌 badge, and the
"Full breakdown with the raw tool manifests" line). That file does not exist in the site repo.

The real page is `prompts-and-mcp.html`.

- [ ] Repoint both references to `https://karun99.github.io/prompts-and-mcp.html`
- [ ] Or create `mcp-servers.html` and add it to nav + `sitemap.xml` + `llms.txt`

### 4. Tracked-repo coverage is 11 of 48

`tools/trl/projects.json` lists 11 repos. The account has 48. The other 37 get no TRL
scoring at all, including high-visibility ones: `s-ai`, `karun99.github.io`, `neural-harness`,
`buildbot`'s sibling `glama-mcp`, `Arogya`, `techlearn`, `nskprofile`, `ScholarSync`, `QuestWrite`.

- [ ] Decide the intended set — all public non-fork repos is the defensible default
- [ ] Add them to `projects.json`
- [ ] Re-baseline: with 48 repos the table becomes long, consider grouping by domain

---

## MAJOR — `karun99.github.io` navigation

### 5. `works.html` has a different nav than every other page

The 8 main pages share one identical 10-link nav. `works.html` has 12 links:
it is **missing `about.html` and `contact.html`**, and instead carries
`llms.txt`, `sitemap.xml`, `robots.txt` inside the user-facing nav bar.

- [ ] Restore the standard 10-link nav on `works.html`
- [ ] If the machine files belong in a footer, move them there site-wide
- [ ] Fix the root cause: the nav is copy-pasted per page instead of templated

### 6. `profile.html` and `seoreport.html` have no `<nav>` and no `<header>`

Verified: `grep -c '<nav'` → `0` for both, and `grep -c '<header'` → `0` for both.
Both are `index, follow`, self-canonical, and listed in `sitemap.xml`
(profile priority 0.7, seoreport 0.6). A visitor landing on either is stranded.

- [ ] Give both the standard header + nav
- [ ] If they are deliberately standalone, mark them `noindex` and drop them from the sitemap

### 7. `seoreport.html` is an orphan page

No page links to it. `grep -l 'seoreport.html' *.html` matches only itself (its own canonical).
It is in `llms.txt:77` and in the sitemap, but has zero internal inbound links.

- [ ] Link it from `profile.html` (it is an identity-adjacent tool) and/or a footer on every page
- [ ] Remove the `href="#"` placeholder in its body

### 8. `llms-full.txt` is not the full text of every page

`llms.txt:5` states "The full text of every page is at …/llms-full.txt", but
`llms-full.txt` omits `profile.html` and `seoreport.html` — 2 of 11 pages.

- [ ] Append the missing two pages
- [ ] Better: generate `llms-full.txt` in the TRL/workflow pipeline so it cannot drift

---

## MINOR

- [ ] **Mixed path style.** `assets/css/style.css` is relative, but `/favicon.png`,
      `/assets/img/*`, `/site.webmanifest`, `/llms.txt` are root-relative. Valid on root
      GitHub Pages, but the site cannot be previewed from `file://` or hosted on a subpath.
      Pick one. (This is 184 of the 197 flags in the audit — cosmetic, not broken.)
- [ ] `sitemap.xml` declares `xmlns:image` but emits no `<image:image>` elements. Drop the
      unused namespace or add the image tags.
- [ ] TRL table timestamp reads `2026-09-28 03:05 UTC` while the workflow runs every 6 hours.
      It has not refreshed in 3 days — check the last workflow run.
- [ ] `tools/trl/trl_tracker.py:336` — the comment contradicts the code:
      `return 0 if not failed else 1  # 0 even on partial failures; report count below`
- [ ] `tools/trl/trl_tracker.py:206` — the dict key `stars` holds a TRL level marker
      (`TRL_STARS[level-1] + f" {level}"`), not a star count. Rename to `level_marker`.
- [ ] `.github/workflows/trl-tracker.yml` pushes straight to `main`; if branch protection is
      enabled the scheduled job will fail. Confirm protection state or switch to a PR.

---

## NIT / POLICY

- [ ] The `md5`-gated project manager in `assets/js/main.js` is a **client-side** gate. The
      uncommitted diff already removed the `admin`/`admin` backdoor and added a comment
      stating it is a convenience lock, not a security boundary — that is correct, keep it.
      Credential is `MD5("2")` for user `nsk`; verified the digest matches.
      Consider dropping the login UI entirely, since `localStorage` is visitor-local anyway.
- [ ] `karun99.github.io/.mcp.json` is committed and references `${GLAMA_API_KEY}`. No secret
      is inlined, so it is safe — but confirm `GLAMA_API_KEY` is never committed anywhere.

---

## Verified clean (no action)

- **HTML structure** — 0 unclosed tags, 0 stray closers, 0 duplicate `id`s across all 11 pages.
- **Heading hierarchy** — exactly one `<h1>` per page, no level skips.
- **Metadata** — every page has `title`, `description`, `og:title`, `og:description`,
  `og:image`, `twitter:card`, `canonical`, and `robots`.
- **Canonicals** — all 11 self-referential and consistent with `sitemap.xml`; no `noindex`
  page is listed in the sitemap.
- **Links** — 0 dead internal links, 0 dead relative asset references, 0 broken anchors
  (including cross-page fragments).
- **Images** — 0 missing `alt` attributes.
- **JS syntax** — `node --check assets/js/main.js` passes.
- **`assets/js/main.js` uncommitted diff** — good quality: extracts `readStoredProjects()`
  to dedupe four copies of the same try/catch parse, fixes a real bug where
  `renderProjects` sorted `DEFAULT_PROJECTS` in place via `Array.sort`, adds an
  empty-credential guard, and stops logging the attempted username. Keep all of it.
- **`robots.txt`** — well-formed, explicit allow-list for ~30 AI/answer-engine crawlers,
  correct `Sitemap:` directive.
- **`profile.html` / `seoreport.html` link targets** — all resolve.
- **No committed secrets** in either repo.
- **README.md** — 0 dead relative links, balanced code fences (10).
