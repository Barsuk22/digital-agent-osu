@echo off
setlocal
cd /d D:\Projects\digital_agent_osu_project

powershell -ExecutionPolicy Bypass -File ".\external\osu_lazer_controller\start_bridge.ps1" %*
