@echo off
echo ====================================
echo   InfoSeek - Service Status Check
echo ====================================
echo.

echo Checking Docker containers...
docker-compose ps

echo.
echo ====================================
echo Checking service health...
echo ====================================
echo.

echo [1/5] Checking PostgreSQL...
docker-compose exec -T db pg_isready -U postgres
if errorlevel 1 (
    echo [ERROR] PostgreSQL is not ready!
) else (
    echo [OK] PostgreSQL is ready
)

echo.
echo [2/5] Checking Redis...
docker-compose exec -T redis redis-cli ping
if errorlevel 1 (
    echo [ERROR] Redis is not responding!
) else (
    echo [OK] Redis is responding
)

echo.
echo [3/5] Checking Selenium...
curl -s http://localhost:4444/wd/hub/status >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Selenium is not accessible!
) else (
    echo [OK] Selenium is accessible
)

echo.
echo [4/5] Checking Django Backend...
curl -s http://localhost:8000/api/tasks/ >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Django backend is not responding!
) else (
    echo [OK] Django backend is responding
)

echo.
echo [5/5] Checking Celery Worker...
docker-compose exec -T celery_worker celery -A infoseek inspect active >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Cannot check Celery worker status
    echo Try: docker-compose logs celery_worker
) else (
    echo [OK] Celery worker is running
)

echo.
echo ====================================
echo   Recent Celery Worker Logs
echo ====================================
docker-compose logs --tail=20 celery_worker

echo.
echo ====================================
echo   Recent Backend Logs
echo ====================================
docker-compose logs --tail=20 backend

echo.
pause

