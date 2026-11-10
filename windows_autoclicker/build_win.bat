@echo off
rem Windows one-click build: double-click this file
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_win.ps1" %*
