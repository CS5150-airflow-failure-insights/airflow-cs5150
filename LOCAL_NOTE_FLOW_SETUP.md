# Local Note Flow Setup

This file records the steps and changes used to get the local Airflow note flow working end to end.

## Goal

Run Airflow locally, trigger a DAG/task log flow, save an error note from the UI, and confirm that it is written to the backend database.

## What Was Wrong Initially

- The Python environment was running an older installed Airflow release instead of this repo's code.
- The local metadata DB did not fully match the branch's models/migrations.
- The main Airflow frontend bundle was not built, so `http://127.0.0.1:8080/` returned `Internal Server Error`.
- The simple auth login frontend bundle was not built, so `/auth/login` also returned `Internal Server Error`.
- The note modal UI existed, but the Save Note button only logged to the console and did not call the backend.
- There was a duplicate model/migration setup for `error_note` and `error_signature`, which interfered with migrations.

## Environment Fixes

### Python / backend

- Switched the local environment to use this repo's Airflow code rather than the old installed package.
- Installed local editable packages for:
  - `apache-airflow-core`
  - `apache-airflow-task-sdk`
- Updated backend dependencies needed by this branch, including FastAPI/Cadwyn compatibility.
- Ran Airflow DB migration against:
  - `/Users/srutigudapati/Desktop/airflow-cs5150/.airflow_home/airflow.db`

### Frontend assets

Built the main Airflow UI:

- source: `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/ui`
- output: `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/ui/dist`

Built the simple auth login UI:

- source: `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/api_fastapi/auth/managers/simple/ui`
- output: `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/api_fastapi/auth/managers/simple/ui/dist`

These builds were required so the backend served UI on `8080` could load correctly.

## Code Changes Made

### 1. Main UI dev server support

Updated:

- `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/ui/vite.config.ts`

Changes:

- Added a dev-only transform so Vite serves a valid `<base href="/">` instead of the unresolved backend template placeholder.
- Added a `/api` proxy to `http://localhost:8080` for local frontend dev use.

This helped local frontend debugging, but for normal use the backend-served UI on `8080` is the correct app.

### 2. Duplicate error note model cleanup

Updated:

- `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/models/error_note.py`
- `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/models/error_signature.py`
- `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/migrations/versions/0101_3_2_0_add_error_notes_and_signatures.py`

Changes:

- Made `error_note.py` and `error_signature.py` compatibility re-exports of the canonical models from `error_insight.py`.
- Turned the duplicate migration into a no-op.
- Adjusted the migration chain so Alembic did not end up with conflicting heads for the same tables.

### 3. Save Note button wiring

Updated:

- `/Users/srutigudapati/Desktop/airflow-cs5150/airflow-core/src/airflow/ui/src/pages/TaskInstance/Logs/TaskLogContent.tsx`

Changes:

- Replaced the placeholder `console.log` save handler with a real API call.
- Used the logged-in user's `username` as the `author`.
- Sent the note payload to the backend UI route:
  - `POST /ui/error-notes`
- Added success and error toasts.
- Disabled repeated submits while the save request is in flight.

## Final Working Flow

### Run locally

Use the backend-served app:

- `http://127.0.0.1:8080`

Login:

- username: `admin`
- password stored in:
  - `/Users/srutigudapati/Desktop/airflow-cs5150/.airflow_home/simple_auth_manager_passwords.json.generated`

### Save a note

1. Open a DAG run and go to a task instance log.
2. Highlight error or log text.
3. Click the small note icon.
4. Enter note text.
5. Click `Save Note`.

### Verify in DB

Check notes:

```bash
sqlite3 /Users/srutigudapati/Desktop/airflow-cs5150/.airflow_home/airflow.db "
SELECT id, author, note_text, created_at
FROM error_note
ORDER BY created_at DESC
LIMIT 10;
"
```

Check linked signature/regex:

```bash
sqlite3 /Users/srutigudapati/Desktop/airflow-cs5150/.airflow_home/airflow.db "
SELECT n.id, n.note_text, s.signature_canonical, s.signature_regex
FROM error_note n
JOIN error_signature s ON s.id = n.signature_id
ORDER BY n.created_at DESC
LIMIT 5;
"
```

## Verified Result

Confirmed working with:

- `error_note.id = 1`
- `author = admin`
- `note_text = skipped note text`

And linked signature:

- `signature_canonical = Task was skipped`
- `signature_regex = Task\ was\ skipped`

## Summary

The final working path is:

- frontend log modal
- `POST /ui/error-notes`
- backend signature resolution
- DB insert into `error_note`
- DB link to `error_signature`

This is now a real frontend-to-API-to-backend flow.
