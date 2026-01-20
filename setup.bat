@echo off
echo ====================================
echo   InfoSeek - First Time Setup
echo ====================================
echo.

echo [1/3] Checking Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed or not in PATH!
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo [OK] Docker is installed

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed or not in PATH!
    pause
    exit /b 1
)
echo [OK] Docker Compose is installed
echo.

echo [2/3] Starting all services...
echo This may take several minutes on first run...
docker-compose up --build -d
if errorlevel 1 (
    echo [ERROR] Failed to start services!
    pause
    exit /b 1
)
echo [OK] Services started
echo.

echo [3/3] Waiting for database to be ready...
timeout /t 10 /nobreak >nul
echo Running database migrations...
docker-compose exec -T backend python manage.py migrate
if errorlevel 1 (
    echo [WARNING] Migrations failed. You may need to run them manually:
    echo docker-compose exec backend python manage.py migrate
) else (
    echo [OK] Migrations completed
)
echo.

echo ====================================
echo   Setup Complete!
echo ====================================
echo.
echo Services are starting up. Please wait a moment for all services to be ready.
echo.
echo You can check service status with: check-services.bat
echo.
echo Access points:
echo   - Frontend: http://localhost:3000
echo   - Backend API: http://localhost:8000
echo   - Django Admin: http://localhost:8000/admin
echo.
echo To view logs: docker-compose logs -f
echo To stop services: docker-compose down
echo.
pause

