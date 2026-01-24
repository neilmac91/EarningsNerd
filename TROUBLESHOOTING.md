# Troubleshooting Guide

This document provides solutions to common development issues encountered while working on EarningsNerd.

## Frontend Issues

### "Something went wrong!" Error Page

**Symptoms:**
- Application displays a generic error page
- Browser console shows 500 errors for static assets (`/_next/static/chunks/*.js`)
- Error message: `Cannot find module './[number].js'`

**Root Cause:**
Next.js webpack build cache corruption. This typically occurs when:
- The dev server is force-quit or crashes during a build
- Switching git branches while the dev server is running
- Running multiple dev servers simultaneously
- File system conflicts or disk issues

**Solution:**
```bash
# Stop the dev server (Ctrl+C or kill the process)
# Unix/macOS:
pkill -f "next dev"
# Windows:
# taskkill /F /IM node.exe

# Clear the build cache
cd frontend
npm run clean

# Restart the dev server
npm run dev
```

**Prevention:**
- Always gracefully stop the dev server before switching git branches
- Use `npm run dev:clean` if you suspect cache issues
- Avoid running multiple dev servers on the same codebase

---

### Module Resolution Errors

**Symptoms:**
- Import errors for installed packages
- `Cannot find module` errors in the console

**Solution:**
```bash
# Clear all caches and reinstall dependencies
cd frontend
npm run clean:all
# Remove node_modules (cross-platform with rimraf if installed globally, or use npx)
npx rimraf node_modules
npm install
```

---

### Port Already in Use

**Symptoms:**
- Error: `Port 3000 is already in use`

**Solution:**
```bash
# Find and kill the process using port 3000

# Unix/macOS:
lsof -ti:3000 | xargs kill -9

# Windows (Command Prompt):
# netstat -ano | findstr :3000
# taskkill /PID <PID> /F

# Or use a different port
PORT=3001 npm run dev
# Windows (PowerShell):
# $env:PORT=3001; npm run dev
```

---

## Backend Issues

### Database Connection Errors

**Symptoms:**
- `sqlalchemy.exc.OperationalError: unable to open database file`

**Solution:**
```bash
# Ensure the database file exists
cd backend
python -c "from app.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

---

### API Not Responding

**Symptoms:**
- Frontend shows network errors
- Backend is not accessible at `http://localhost:8000`

**Solution:**
```bash
# Check if the backend is running
# Unix/macOS:
lsof -i :8000
# Windows:
# netstat -ano | findstr :8000

# If not running, start it
cd backend
uvicorn main:app --reload
```

---

## General Development Tips

### Clean Slate Restart

If you're experiencing persistent issues, try a complete clean restart:

```bash
# Stop all services
# Unix/macOS:
pkill -f "next dev"
pkill -f "uvicorn"
# Windows:
# taskkill /F /IM node.exe
# taskkill /F /IM python.exe

# Frontend cleanup
cd frontend
npm run clean:all
npx rimraf node_modules
npm install

# Backend cleanup (if needed)
cd ../backend
npx rimraf __pycache__
npx rimraf .pytest_cache

# Restart services
# Terminal 1: Backend
cd backend
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Checking Service Status

```bash
# Check what's running on common ports
# Unix/macOS:
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
# Windows:
# netstat -ano | findstr :3000
# netstat -ano | findstr :8000

# Check running Node processes
# Unix/macOS:
ps aux | grep node
# Windows:
# tasklist /FI "IMAGENAME eq node.exe"

# Check running Python processes
# Unix/macOS:
ps aux | grep python
# Windows:
# tasklist /FI "IMAGENAME eq python.exe"
```

---

## Getting Help

If you encounter an issue not covered here:

1. Check the browser console for detailed error messages
2. Check the terminal output for both frontend and backend
3. Review recent git commits for breaking changes
4. Check the GitHub Issues for similar problems
5. Create a new issue with:
   - Error message and stack trace
   - Steps to reproduce
   - Environment details (OS, Node version, Python version)
