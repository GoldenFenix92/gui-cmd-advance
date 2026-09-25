@echo off
cd /d "%~dp0"
if not exist .venv (
    echo Creando entorno virtual...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo Instalando dependencias...
pip install -r requirements.txt
echo Iniciando aplicacion...
python main.py
pause
