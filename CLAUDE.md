# CLAUDE.md

## Standing rule: keep PROJECT_CONTEXT.md current

`PROJECT_CONTEXT.md` is the living record of this project: its context, current state, and timeline.

**After every user prompt**, before ending the turn, update `PROJECT_CONTEXT.md`:
1. Add a row to **7. Timeline / History**: the date/time (IST), a short summary of the prompt, and the outcome
   (files changed, commit hashes, failures).
2. Update **5. Current State of the Repository**, **6. Open Items / Next Steps**, and the
   **Last updated** date if anything changed.
3. If the project's scope, MVP, or architecture changes, edit sections 1–4 to match.

Never delete past timeline entries. Correct them only if they are wrong, and say so in the new entry.

## Environment

- `git` is not on PATH. Use `%LOCALAPPDATA%\GitHubDesktop\app-3.6.7\resources\app\git\cmd\git.exe`.
- Pushing over HTTPS from a Claude session fails because there's no GitHub login. The user pushes via GitHub Desktop.
