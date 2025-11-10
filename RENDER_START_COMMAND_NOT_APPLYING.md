# Render Start Command Not Applying - Troubleshooting

## Problem
Changed start command in Render dashboard, but logs still show:
```
==> Running 'uvicorn app.main:app --host 0.0.0.0 --port 10000'
ERROR: Error loading ASGI app. Could not import module "app.main".
```

## Possible Causes

1. **Change didn't save properly**
2. **Render cached the old setting**
3. **Multiple places to set the command**
4. **Service needs manual redeploy after change**

## Solutions

### Solution 1: Verify Settings Are Saved

1. Go to Render Dashboard → Your Service
2. Click on "Settings" tab
3. Scroll down to "Build & Deploy" section
4. Verify **Start Command** field shows exactly:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
5. If it shows `app.main:app`, change it and click "Save Changes"
6. Wait for the page to reload/confirm the save

### Solution 2: Clear and Re-enter

1. Delete the entire start command
2. Type it fresh: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Make sure there are no extra spaces or characters
4. Click "Save Changes"
5. Wait 10-30 seconds for Render to process

### Solution 3: Manual Redeploy

After changing the start command:
1. Go to "Manual Deploy" section
2. Click "Clear build cache & deploy"
3. Or click "Deploy latest commit"
4. This forces Render to use the new settings

### Solution 4: Check Root Directory

While you're in Settings, also verify:
- **Root Directory** is set to: `backend`
- This is critical - if root directory is wrong, the start command won't work

### Solution 5: Check for Environment-Specific Overrides

1. Go to "Environment" tab
2. Look for any environment variables that might override the start command
3. Check for variables like `START_COMMAND` or similar
4. Remove them if they exist

### Solution 6: Recreate Service (Last Resort)

If nothing works:
1. Note down all your environment variables
2. Delete the current service
3. Create a new service from "Blueprint"
4. Connect your GitHub repository
5. Render will automatically use `render.yaml` with correct settings

## Verification Steps

After making changes:

1. **Wait 1-2 minutes** for Render to process
2. **Check the logs** - you should see:
   ```
   ==> Running 'uvicorn main:app --host 0.0.0.0 --port 10000'
   ```
   NOT:
   ```
   ==> Running 'uvicorn app.main:app --host 0.0.0.0 --port 10000'
   ```

3. **If it still shows `app.main:app`**, the setting didn't save - try Solution 2 or 3

## Quick Checklist

- [ ] Start Command is exactly: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Root Directory is: `backend`
- [ ] Clicked "Save Changes" and waited for confirmation
- [ ] Triggered a manual redeploy after saving
- [ ] Checked logs to verify new command is being used

## Expected Behavior

Once the start command is correct, you should see in logs:
```
==> Running 'uvicorn main:app --host 0.0.0.0 --port 10000'
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:10000 (Press CTRL+C to quit)
```

