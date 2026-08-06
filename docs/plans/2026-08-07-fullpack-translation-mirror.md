# Full-pack Translation Mirror Implementation Plan

**Goal:** Publish a full-pack manifest whose translation archives remain downloadable, and refresh it after each successful upstream sync.

**Scope:** Mirror only `GTNewHorizons/GTNH-Translations` archives referenced by the generated daily manifest, retain two generations, and connect publication to real upstream merges. The manifest format and Gradle consumer do not change.

**Approach:** Add one focused publishing CLI beside the existing manifest CLI. It uses the repository GitHub token and the installed GitHub CLI to upload release assets, rewrites the local JSON only after every required archive is mirrored, publishes that JSON, then deletes generations older than the newest two. The sync workflow invokes the manifest workflow after the merged commit is visible on `master`.

**Constraints:** Keep versioned translation filenames because Gradle caches by URL. Publish assets before the manifest and clean up only afterward. Keep `workflow_dispatch`, remove the independent daily schedule, require no personal token, and put all automated tests in the final commit.

**Acceptance criteria:** Every translation URL in the published manifest resolves from `Pxx500/DreamAssemblerXXL`; unrelated archive URLs remain unchanged; the release retains the newest two translation generations; a failed mirror does not replace the previous manifest; and a no-op upstream sync does not dispatch publication.

**Risks or decisions:** A generation is the version suffix already present in translation filenames, such as `2026-08-06+413`. Cleanup applies only to mirrored translation assets matching that established filename shape, not to `daily.json` or unrelated release assets.

### Task 1: Add atomic translation mirroring and manifest publication

**Purpose:** Make the published manifest independent of moving translation release assets.

**Affected areas:** New focused module under `src/daxxl/` for manifest publication, a matching command under `src/daxxl/cli/`, and existing manifest path constants where useful.

**Requirements:**

- Read the generated full-pack `daily.json` and select only archive entries whose parsed GitHub owner/repository are exactly `GTNewHorizons/GTNH-Translations`.
- Download the exact versioned filenames referenced by those URLs and upload them to the current repository's `fullpack-daily` release.
- Reuse an already-uploaded asset with the same filename instead of downloading or uploading it again.
- Rewrite selected URLs to the current repository's versioned release asset URLs only after all required assets are present.
- Upload the rewritten manifest after the archive uploads; then delete matching translation assets outside the newest two filename generations.
- Propagate translation download and upload failures before replacing the published manifest.
- Use `GITHUB_TOKEN`/`GH_TOKEN` supplied by GitHub Actions and `GITHUB_REPOSITORY`; add no secret or compatibility path.

**Implementation notes:** Keep URL selection, filename/generation parsing, manifest rewriting, and retention selection as small pure functions. Keep GitHub release operations in the CLI boundary using the already-available `gh` executable rather than introducing another client layer or dependency.

**Verification:** Run `uv run ruff check src/daxxl` and `uv run ty check src/daxxl` after the production code is in place. Exercise the CLI against a temporary manifest with GitHub operations replaced by a harmless local command seam before wiring the live workflow.

**Commit boundary:** `Mirror full-pack translation archives`

### Task 2: Publish after upstream synchronization

**Purpose:** Refresh the manifest from the same repository state that was just synchronized from upstream.

**Affected areas:** `.github/workflows/fullpack-manifest.yml` and `.github/workflows/sync-upstream.yml`.

**Requirements:**

- Replace the current direct manifest upload with the new publishing command.
- Keep manual dispatch and remove the standalone daily cron.
- After the sync merge request succeeds, wait until the merged head is visible on `master`, then dispatch `fullpack-manifest.yml` on `master` through `workflow_dispatch`.
- Do not dispatch when `upstream/master` was already contained in the fork's `master`, or when the merge fails.
- Keep existing concurrency and repository-token permissions sufficient for release publication and workflow dispatch.

**Implementation notes:** Do not treat an asynchronous `enqueued` response alone as proof that `master` contains the merge. Re-fetch the branch until the expected sync head is present before dispatching, with the same bounded polling style already used by the sync workflow.

**Verification:** Validate both YAML files with the repository's available workflow/YAML tooling, inspect the resulting trigger and permission structure, and run the publishing workflow manually once after tests pass.

**Dependencies:** Task 1.

**Commit boundary:** `Publish full-pack manifest after upstream sync`

### Task 3: Add the complete automated test set

**Purpose:** Protect URL rewriting, safe publication ordering, retention, and sync-trigger behavior in one removable final commit.

**Affected areas:** New focused publishing tests under `tests/`, existing `tests/test_fullpack_manifest.py` only if shared manifest assertions need adjustment, and workflow text tests if no established workflow test harness exists.

**Requirements:**

- Prove that only exact GTNH-Translations release URLs are selected and unrelated archives stay byte-for-byte equivalent after rewriting.
- Prove that versioned filenames become fork release URLs and already-present assets are reused.
- Prove that the newest two distinct generations are retained and `daily.json`, unrelated assets, and current manifest assets are never selected for deletion.
- Prove that a download/upload failure happens before manifest upload.
- Prove that upstream no-op and failure paths do not dispatch, while a confirmed merged `master` does.
- Keep every automated test change in this final commit.

**Verification:** Run `uv run pytest`, `uv run ruff check .`, and `uv run ty check src tests`. Then run the GitHub workflow manually, fetch the published manifest, issue a request to every translation URL, and confirm zero `404` responses and at most two mirrored generations in the release.

**Dependencies:** Tasks 1 and 2.

**Commit boundary:** `Test full-pack translation mirroring`
