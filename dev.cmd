@echo off
setlocal
set "PYTHONPATH=%~dp0src"
python -m projectdock %*
exit /b %errorlevel%
