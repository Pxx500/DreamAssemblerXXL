# Full-pack translation mirror

## Goal

Keep every URL in the published full-pack manifest downloadable even when
GTNH-Translations replaces assets on its moving `*-latest` releases. Also
regenerate the manifest immediately after this fork successfully syncs new
upstream changes.

## Design

The existing manifest generator continues to describe the resolved daily
client. A small publishing tool reads that generated manifest and processes
only archive URLs from `GTNewHorizons/GTNH-Translations`.

For each translation archive, the tool downloads the exact asset named by the
manifest and uploads it to this repository's `fullpack-daily` release under its
original versioned filename. It then replaces the archive URL in the local
manifest with the corresponding release URL from this repository. Versioned
filenames are retained because the Gradle cache uses the URL as the cache key.

The workflow publishes in this order:

1. Generate the manifest.
2. Mirror all translation archives required by it.
3. Upload the rewritten manifest.
4. Remove mirrored translations older than the two newest generations.

Publishing the manifest after its assets prevents it from ever pointing at
files that have not been uploaded yet. Cleanup happens last and retains two
complete generations, normally about 56 MiB in total.

The upstream sync workflow dispatches the full-pack manifest workflow only
after GitHub confirms that a pull request containing new upstream changes was
merged. A no-op sync does not dispatch it. The manifest workflow keeps its
manual trigger; its daily schedule is removed because successful upstream sync
is now the source of fresh data.

## Failure behavior

A failed translation download or upload stops publication before the manifest
is replaced, so the previously published manifest remains usable. Cleanup
failure fails the workflow but does not invalidate the newly published
manifest, because cleanup must never select either of the two retained
generations.

The workflow uses only the repository-provided GitHub token. No personal token
or additional secret is required.

## Verification

Automated tests cover translation URL recognition, rewritten URLs, versioned
asset names, two-generation retention, and leaving unrelated archives
unchanged. Workflow tests or focused script checks cover dispatch only after a
confirmed upstream merge and publication order.

After deployment, run the workflow once and verify that every translation URL
in the published `daily.json` returns a successful response and that the
release contains no more than two translation generations.
