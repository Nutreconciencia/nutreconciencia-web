V30 — ORCID duplicate-safe generator

1) Replace ONLY:
   scripts/sync_orcid.py
   with sync_orcid_V30.py

2) Do NOT change:
   .github/workflows/sync-orcid.yml

3) Commit:
   Update ORCID generator V30

4) Run:
   Actions → Sync ORCID publications → Run workflow

5) After the workflow succeeds, use dedupe_orcid.py to consolidate current
   duplicate ORCID folders. The cleanup keeps a canonical folder and turns
   duplicate folders into noindex/canonical redirect stubs, rather than
   deleting them abruptly.

Important:
Do not manually delete duplicate folders before the V30 run.
