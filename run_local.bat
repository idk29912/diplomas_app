@echo off
REM ================================
REM Script para iniciar Flask en local
REM ================================

echo Iniciando el servidor Flask...

REM Activar entorno virtual si existe
IF EXIST .venv (
    call .venv\Scripts\activate
)

REM Ejecutar Flask en modo debug en puerto 5000
python -m flask --app app run --debug --port 5000

REM Abrir navegador automáticamente
start http://127.0.0.1:5000

pause
