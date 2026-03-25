@echo off
REM Zwesta Trading v2 - Build All Components (Windows)
REM This script builds everything: Backend, Frontend, Mobile, Docker containers

setlocal enabledelayedexpansion

echo.
echo ==========================================
echo Zwesta Trading v2 - Complete Build
echo ==========================================
echo.

REM Get script directory
for %%I in ("%~dp0.") do set SCRIPT_DIR=%%~fI

set BACKEND_DIR=%SCRIPT_DIR%\backend
set FRONTEND_DIR=%SCRIPT_DIR%\frontend
set MOBILE_DIR=%SCRIPT_DIR%\mobile
set DOCKER_DIR=%SCRIPT_DIR%\docker

REM Get build options
set BUILD_BACKEND=%1
if "%BUILD_BACKEND%"=="" set BUILD_BACKEND=all
set BUILD_FRONTEND=%2
if "%BUILD_FRONTEND%"=="" set BUILD_FRONTEND=all
set BUILD_MOBILE=%3
if "%BUILD_MOBILE%"=="" set BUILD_MOBILE=all
set BUILD_DOCKER=%4
if "%BUILD_DOCKER%"=="" set BUILD_DOCKER=all

REM ===== BACKEND BUILD =====
if "%BUILD_BACKEND%"=="all" (
    echo.
    echo ==========================================
    echo Building Backend
    echo ==========================================
    echo.
    
    if not exist "%BACKEND_DIR%" (
        echo ERROR: Backend directory not found: %BACKEND_DIR%
        goto error
    )
    
    cd /d "%BACKEND_DIR%"
    
    REM Create .env if it doesn't exist
    if not exist ".env" (
        echo Creating .env from .env.example
        copy .env.example .env >nul
        echo Edit .env with your credentials
    )
    
    REM Show Python version
    python --version
    
    REM Install dependencies
    echo.
    echo Installing Python dependencies...
    pip install -q -r requirements-minimal.txt
    if errorlevel 1 (
        echo Warning: Some dependencies may require compilation
        pip install -r requirements-minimal.txt
    )
    
    echo ✓ Backend build complete!
    cd /d "%SCRIPT_DIR%"
)

REM ===== FRONTEND BUILD =====
if "%BUILD_FRONTEND%"=="all" (
    echo.
    echo ==========================================
    echo Building Frontend
    echo ==========================================
    echo.
    
    if not exist "%FRONTEND_DIR%" (
        echo ERROR: Frontend directory not found: %FRONTEND_DIR%
        goto error
    )
    
    cd /d "%FRONTEND_DIR%"
    
    REM Check Node.js
    where node >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Node.js not found. Install from https://nodejs.org/
        goto error
    )
    
    node --version
    
    REM Install dependencies
    if not exist "node_modules" (
        echo Installing Node.js dependencies...
        call npm install
    ) else (
        echo Node.js dependencies already installed
    )
    
    REM Build
    echo Building React app...
    call npm run build
    
    echo ✓ Frontend build complete!
    cd /d "%SCRIPT_DIR%"
)

REM ===== MOBILE BUILD =====
if "%BUILD_MOBILE%"=="all" (
    echo.
    echo ==========================================
    echo Building Mobile App
    echo ==========================================
    echo.
    
    if not exist "%MOBILE_DIR%" (
        echo ERROR: Mobile directory not found: %MOBILE_DIR%
        goto error
    )
    
    cd /d "%MOBILE_DIR%"
    
    REM Check Flutter
    where flutter >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Flutter not found. Install from https://flutter.dev/
        goto error
    )
    
    flutter --version
    
    REM Get dependencies
    echo Getting Flutter dependencies...
    call flutter pub get
    
    REM Build APK
    echo Building Android APK ^(Release^)...
    call flutter build apk --release --no-android-gradle-daemon
    
    if exist "build\app\outputs\flutter-apk\app-release.apk" (
        echo ✓ APK built: build\app\outputs\flutter-apk\app-release.apk
    )
    
    echo ✓ Mobile build complete!
    cd /d "%SCRIPT_DIR%"
)

REM ===== DOCKER BUILD =====
if "%BUILD_DOCKER%"=="all" (
    echo.
    echo ==========================================
    echo Building Docker Images
    echo ==========================================
    echo.
    
    if not exist "%DOCKER_DIR%" (
        echo ERROR: Docker directory not found: %DOCKER_DIR%
        goto error
    )
    
    REM Check Docker
    where docker >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Docker not found. Install from https://www.docker.com/
        goto error
    )
    
    docker --version
    docker-compose --version
    
    REM Build images
    echo Building Backend image...
    docker build -f "%DOCKER_DIR%\Dockerfile.backend" -t zwesta/backend:latest .
    
    echo Building Frontend image...
    docker build -f "%DOCKER_DIR%\Dockerfile.frontend" -t zwesta/frontend:latest .
    
    echo Building Mobile image...
    docker build -f "%DOCKER_DIR%\Dockerfile.mobile" -t zwesta/mobile:latest .
    
    echo ✓ Docker build complete!
    
    REM List images
    echo.
    echo Built images:
    docker images | findstr zwesta
)

REM Final status
echo.
echo ==========================================
echo Build Summary
echo ==========================================
echo ✓ All builds complete!
echo.
echo Next steps:
echo 1. Backend: cd backend ^&^& python app_simple.py
echo 2. Frontend: cd frontend ^&^& npm run dev
echo 3. Mobile: cd mobile ^&^& flutter run
echo 4. Docker: docker-compose up -d
echo.
echo For more info, see: INDEX.md or QUICK_START.md
echo.
pause
goto end

:error
echo.
echo Build failed!
pause
exit /b 1

:end
endlocal
