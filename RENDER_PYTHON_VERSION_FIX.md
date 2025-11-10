# Render Python Version Fix

## Problem
Render is using Python 3.13.4 instead of Python 3.11.9, causing pydantic-core build failures.

## Root Cause
- Render may not automatically detect `runtime.txt` when service was created manually
- Services created via dashboard don't automatically use `render.yaml`
- Python version might be cached from previous deployments

## Solutions

### Solution 1: Set Python Version in Render Dashboard (Immediate Fix)

1. Go to your Render service dashboard
2. Click on "Settings" tab
3. Scroll to "Environment" section
4. Look for "Python Version" or "Runtime" setting
5. Set it to `3.11.9` explicitly
6. Save changes
7. Trigger a new deployment

### Solution 2: Use Blueprint/Infrastructure as Code (Recommended)

1. Delete existing service (or create a new one)
2. In Render Dashboard: "New" → "Blueprint"
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml`
5. This ensures `runtime.txt` is properly read

### Solution 3: Verify runtime.txt Location

Ensure `runtime.txt` exists at the **repository root** (not in `backend/`):
```
EarningsNerd/
  ├── runtime.txt          ← Must be here (repository root)
  ├── render.yaml
  └── backend/
      ├── requirements.txt
      └── ...
```

Contents of `runtime.txt`:
```
python-3.11.9
```

### Solution 4: Use Updated pydantic (Works with Python 3.13)

If Render continues to use Python 3.13, the updated `requirements.txt` uses:
- `pydantic>=2.9.0,<3.0.0` - Has pre-built wheels for Python 3.13
- `pydantic-settings>=2.4.0,<3.0.0` - Compatible with pydantic 2.9+

This should resolve the build error even with Python 3.13.

## Verification

After applying fix, check deployment logs for:
```
==> Installing Python version 3.11.9...
```

NOT:
```
==> Installing Python version 3.13.4...
```

## Current Status

- ✅ `runtime.txt` exists at repository root
- ✅ `render.yaml` configured with correct settings
- ✅ `requirements.txt` updated to pydantic>=2.9.0 (works with Python 3.13 if needed)
- ⚠️  May need to manually set Python version in Render Dashboard

## Next Steps

1. Try Solution 1 first (set Python version in dashboard)
2. If that doesn't work, try Solution 2 (use Blueprint)
3. If Render still uses Python 3.13, the updated pydantic should work
4. Monitor deployment logs to verify Python version

