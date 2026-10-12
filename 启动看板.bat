@echo off
title AI 知识库看板
cd /d "%~dp0"

rem 已在运行则直接打开页面
netstat -ano | findstr :8787 | findstr LISTENING >nul 2>nul
if %errorlevel%==0 (
    echo [AI 知识库] 看板已在运行，直接打开 http://localhost:8787 ...
    start "" http://localhost:8787
    timeout /t 2 /nobreak >nul
    exit /b 0
)

where node >nul 2>nul
if not %errorlevel%==0 (
    echo [AI 知识库] 未找到 Node.js，请先安装 Node ^>=18 后重试。
    pause
    exit /b 1
)

echo [AI 知识库] 正在启动看板 http://localhost:8787 （关闭本窗口或 Ctrl+C 即停止服务）
rem 等 2 秒让服务起来，再用默认浏览器打开页面
start "" cmd /c "timeout /t 2 /nobreak >nul & start "" http://localhost:8787"
node web/server/index.js

echo.
echo [AI 知识库] 服务已停止。
pause
