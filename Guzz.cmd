@echo off
rem Mo Guzz bang runtime cuc bo; chua chay cai_dat.ps1 thi dung pythonw cua he thong.
setlocal
set "APP=%~dp0"
if exist "%APP%runtime\python\pythonw.exe" (
    start "" "%APP%runtime\python\pythonw.exe" "%APP%gui\main.py" %*
) else (
    start "" pythonw "%APP%gui\main.py" %*
)
