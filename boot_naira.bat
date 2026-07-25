@echo off
color 0A
echo ==========================================
echo       NAIRA OS BOOT SEQUENCE INITIATED
echo ==========================================
echo.

echo [1/2] Powering up Neural Brain (FastAPI Backend)...
start "Naira Backend" cmd /k "venv\Scripts\activate && uvicorn main:app --reload"

echo [2/2] Booting up UI Dashboard (React Frontend)...
start "Naira Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo ==========================================
echo  SYSTEM ONLINE. WAITING FOR OPERATOR.
echo ==========================================
pause