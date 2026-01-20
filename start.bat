@echo off
echo ====================================
echo   InfoSeek - Starting Services
echo ====================================
echo.

echo Checking if services are already running...
docker-compose ps | findstr "Up" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Some services are already running.
    echo.
    choice /C YN /M "Do you want to restart all services"
    if errorlevel 2 (
        echo Cancelled.
        pause
        exit /b 0
    )
    echo Stopping existing services...
    docker-compose down
    echo.
)

echo Starting all services...
docker-compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start services!
    echo.
    echo If this is your first time running the project, use setup.bat instead.
    pause
    exit /b 1
)

echo [OK] Services started
echo.

echo ====================================
echo   Services Starting
echo ====================================
echo.
echo Services are starting up. Please wait a moment for all services to be ready.
echo.
echo Access points:
echo   - Frontend: http://localhost:3000
echo   - Backend API: http://localhost:8000
echo   - Django Admin: http://localhost:8000/admin
echo.
echo Useful commands:
echo   - Check status: check-services.bat
echo   - View logs: docker-compose logs -f
echo   - Stop services: docker-compose down
echo.
pause

