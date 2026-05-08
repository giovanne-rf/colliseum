@echo off
setlocal

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=8000"
set "APP_URL=http://%HOST%:%PORT%"

echo.
echo ========================================
echo  Iniciando Colliseum
echo ========================================
echo.

where uvicorn >nul 2>nul
if errorlevel 1 (
    echo Uvicorn nao encontrado no PATH.
    echo.
    echo Instale as dependencias com:
    echo   pip install -e ".[dev]"
    echo.
    pause
    exit /b 1
)

start "Colliseum" "%APP_URL%/chaves"

echo Servidor: %APP_URL%
echo Docs API: %APP_URL%/docs
echo.
echo Pressione CTRL+C para parar o servidor.
echo.

uvicorn app.main:app --host %HOST% --port %PORT% --reload

endlocal
