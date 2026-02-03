# LiderBPO Auto-Rater - Issues & Blockers

## Task 5: E2E Manual Testing

**Status**: BLOCKED - Requires display/GUI environment

**What was verified programmatically**:
- All 23 tests pass
- All imports work correctly
- Exit codes are correct (1, 2, 3, 4)
- Logo asset exists (16KB PNG)
- RatingWorker is daemon thread

**What requires manual verification**:
1. GUI opens with LiderBPO branding (logo, blue header)
2. Login fields accept input
3. Terminal shows real-time colored logs
4. Worker processes articles correctly
5. Cookies saved to `.suit_storage.json`
6. Second run reuses saved session

**To test manually**:
```bash
uv run scripts/work/rating_lider.py
```

**Credentials**:
- Email: felippe.menezes@liderbpo.com.br
- Password: (from user's earlier message)

**Resolution**: Marking as BLOCKED and proceeding to Task 6 (PyInstaller).
User should run manual E2E test after PyInstaller is complete.
