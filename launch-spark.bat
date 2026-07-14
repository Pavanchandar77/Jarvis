@echo off
title Spark Desktop — Spark
echo.
echo  ==========================================
echo   Spark Desktop — Powered by Spark
echo  ==========================================
echo.

cd /d "%~dp0"

:: Check if node_modules exist
if not exist "node_modules\" (
    echo [Setup] node_modules not found. Running npm install...
    npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed. Make sure Node.js is installed.
        pause
        exit /b 1
    )
)

:: Launch the Electron app
echo [Launch] Starting Spark Desktop...
npm start
