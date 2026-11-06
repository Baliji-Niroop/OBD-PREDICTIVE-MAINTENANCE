@echo off
setlocal
cd /d "%~dp0"
call "%~dp0scripts\windows\Launch_Dashboard.bat"
exit /b %errorlevel%
