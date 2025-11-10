# Render Start Command Fix

## Problem
Build succeeded, but deployment fails with:
```
ERROR: Error loading ASGI app. Could not import module "app.main".
```

## Root Cause
Render is using the wrong start command: `uvicorn app.main:app` instead of `uvicorn main:app`.

This happens when:
1. Render service was created manually (not from render.yaml)
2. Start command in Render dashboard is incorrect
3. Render auto-detected the wrong command

## Solution

### Step 1: Verify Root Directory
In Render Dashboard → Your Service → Settings:
- **Root Directory** must be set to: `backend`

### Step 2: Fix Start Command
In Render Dashboard → Your Service → Settings:
- **Start Command** must be exactly: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**DO NOT USE:**
- ❌ `uvicorn app.main:app` (wrong - tries to import from app.main module)
- ❌ `python main.py` (wrong - doesn't use uvicorn)

**USE:**
- ✅ `uvicorn main:app --host 0.0.0.0 --port $PORT` (correct)

### Step 3: Verify File Structure
With `rootDir: backend`, the structure should be:
```
backend/
  ├── main.py          ← FastAPI app entry point
  ├── app/             ← Application package
  │   ├── __init__.py
  │   ├── database.py
  │   ├── routers/
  │   └── ...
  └── requirements.txt
```

When uvicorn runs from `backend/` directory:
- `main:app` refers to `main.py` (in current directory) and the `app` object inside it
- This works because `main.py` imports from `app.*` (relative to backend/)

### Step 4: Save and Redeploy
1. Save the settings in Render dashboard
2. Render will automatically trigger a new deployment
3. Check logs to verify the correct start command is being used

## Verification

After fixing, you should see in the logs:
```
==> Running 'uvicorn main:app --host 0.0.0.0 --port 10000'
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:10000
```

NOT:
```
==> Running 'uvicorn app.main:app --host 0.0.0.0 --port 10000'
ERROR: Error loading ASGI app. Could not import module "app.main".
```

## Why This Works

- With `rootDir: backend`, all commands run from the `backend/` directory
- `main.py` is in `backend/`, so `uvicorn main:app` can find it
- `main.py` imports `from app.database import ...`, which works because `app/` is a subdirectory of `backend/`
- The `app` object is defined in `main.py` as `app = FastAPI(...)`

## Alternative: Use render.yaml (Recommended)

If you're not using render.yaml, consider recreating the service from a Blueprint:
1. Delete existing service
2. Create new service from Blueprint
3. Connect GitHub repository
4. Render will automatically use `render.yaml` with correct settings

This ensures the start command is always correct.

