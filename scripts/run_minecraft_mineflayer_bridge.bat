@echo off
setlocal

cd /d "%~dp0..\external\minecraft_mineflayer_bridge"

if not exist node_modules (
  echo [minecraft-bridge] node_modules not found, running npm install...
  npm install
  if errorlevel 1 exit /b %errorlevel%
)

echo [minecraft-bridge] starting Mineflayer bridge on 127.0.0.1:4711
npm start
