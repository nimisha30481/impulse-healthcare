# DoseWISE — API Reference

Interactive OpenAPI docs: **http://localhost:8000/api/docs** (schema at `/api/openapi.json`).

Conventions: JSON; session cookie `impulse_session`; send `X-CSRF-Token` (value of the
`impulse_csrf` cookie) on every write. Errors: `{"detail": "...", "errors": [{"field", "message"}]}`.
401 = not signed in / MFA pending, 403 = not authorised (audited), 409 = conflict (stale version,
slot taken, hold expired), 422 = validation, 429 = rate limited.

| Area | Endpoints |
|---|---|
| Auth | `POST /api/auth/register · verify-email · resend-verification · login · mfa/verify · logout · forgot-password · reset-password · demo-login(dev)` · `GET /api/auth/me · session · cognito/login · cognito/callback` |
| Account | `PATCH /api/account/profile · preferences` · `POST password · mfa/setup · mfa/enable · mfa/disable · sessions/revoke-all · close` · `GET sessions · login-history · export` · `DELETE sessions/{id}` |
| Patient data (`/api/patients/{pid}`) | `GET overview · care-team · medications · medications/{item} · doses · adherence · health · records · documents · documents/{id}/download · ocr/{id} · instructions · messages · refills · appointments` · `POST doses/{occ}/respond · records/{id}/correction · documents (multipart) · ocr/{id}/review · instructions/{id}/acknowledge · messages · refills · concerns · emergency · emergency/{id}/acknowledge` · `PATCH health/self-reported` |
| Permissions | `GET /api/me/permissions` · `POST /api/me/caregivers/invite · caregivers/{id}/authorize · caregivers/{id}/revoke · doctors/grant · doctors/{id}/revoke` · `PUT /api/me/caregivers/{id} · escalation-policy` · `POST /api/caregiver/invitations/accept` · `GET /api/caregiver/patients` · `POST /api/break-glass` |
| Doctor | `GET /api/doctor/dashboard · patients · patients/{pid} · prescription-items/{id} · briefs · briefs/{id} · follow-ups · verifications · appointments · availability · slots` · `POST prescriptions · prescription-items/{id}/discontinue · prescription-items/{id}/status · prescription-items/{id}/interaction-check · interaction-preview · interaction-assessments/{id}/review · refills/{id} · corrections/{id} · patients/{pid}/brief · instructions · follow-ups/{id}/complete · verifications/{id} · appointments/{id}/status · leave · slots/{id}/block` · `PUT prescription-items/{id} · availability` |
| Booking | `GET /api/specialities · doctors · doctors/{id}/slots?day=` · `POST /api/appointments/hold · appointments/confirm · appointments/{id}/cancel` · `DELETE /api/appointments/hold/{id}` |
| Support | `GET /api/support/cases · cases/{id}` · `POST cases/{id}/attempts · notes · resolve · escalate` |
| Admin | `GET /api/admin/doctors/pending · audit · break-glass` · `POST doctors/{id}/verify · support-staff · break-glass/{id}/review · fhir-sync/{pid}` |
| Other | `GET /api/notifications · events/stream (SSE) · directory · directory/doctors · integrations/status · health` · `POST notifications/{id}/read · read-all · {id}/acknowledge · dev/run-jobs(dev)` |
