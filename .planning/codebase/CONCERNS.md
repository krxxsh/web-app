# Codebase Concerns

**Analysis Date:** 2026-03-21
**Methodology:** GSD gsd-codebase-mapper (concerns focus)

## Tech Debt

### Deprecated `datetime.utcnow()` Usage
- Issue: Python 3.12+ deprecated `datetime.utcnow()`. Should use `datetime.now(timezone.utc)`.
- Files:
  - `backend/services/scheduling_service.py` (lines 99, 112)
  - `backend/services/logging_service.py` (line 16)
  - `backend/services/fraud_detection.py` (line 28)
  - `backend/services/ai_scheduler.py` (line 102)
  - `backend/ai_engine/engine.py` (line 108)
- Impact: DeprecationWarnings in test output (22 warnings). Will break in future Python versions.
- Fix approach: Replace all with `datetime.now(timezone.utc)` and add `from datetime import timezone`.

### Placeholder Comment in AI Analytics
- Issue: Comment "Placeholder for real parsing logic" at `ai_analytics.py:38`
- Files: `backend/services/ai_analytics.py`
- Impact: Cosmetic only — the actual parsing logic IS implemented on line 40.
- Fix approach: Remove or update the misleading comment.

## Security Considerations

### SECRET_KEY Generation
- Risk: SECRET_KEY falls back to `secrets.token_hex(24)` if env var not set (line 14 of `config.py`).
- Files: `backend/config.py`
- Current mitigation: Uses `os.environ.get()` with cryptographic fallback.
- Recommendations: This is acceptable for local dev but production MUST always set SECRET_KEY env var to prevent session invalidation on restart.

### Firebase Auth Decorator Test Bypass
- Risk: `LOGIN_DISABLED` config flag skips Firebase token verification.
- Files: `backend/utils/auth_helper.py`
- Current mitigation: Only active when explicitly configured in test environments.
- Recommendations: Ensure `LOGIN_DISABLED` is NEVER set in production configurations.

## Performance Bottlenecks

### N+1 Query in Staff Utilization
- Problem: `route_optimal_staff()` runs one query per staff member per day.
- Files: `backend/ai_engine/engine.py` (lines 160-168)
- Cause: Individual appointment count queries per staff inside a loop.
- Improvement path: Use a single aggregate query with `GROUP BY staff_id`.

## Test Coverage Gaps

### Missing Edge Case Tests
- What's not tested: Concurrent booking conflicts, rate limiting, fraud detection thresholds.
- Files: `tests/` directory
- Risk: Race conditions in high-traffic scenarios.
- Priority: Medium

---

*Concerns audit: 2026-03-21 — GSD gsd-codebase-mapper*
