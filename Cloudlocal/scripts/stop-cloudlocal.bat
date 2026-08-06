@echo off
REM Cloudlocal Trading Engine - Stop Script

cd /d "%~dp0.."

echo =============================================
echo  Cloudlocal Trading Engine - Stopping...
echo =============================================
echo.

docker-compose down

echo.
echo All containers stopped.
echo.
pause