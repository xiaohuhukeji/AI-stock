@echo off
chcp 65001 >nul
echo ========================================
echo     QuantDinger SMTP Proxy 启动器
echo ========================================
echo.
echo 正在启动 SMTP 代理服务 (端口 2525)...
echo.

cd /d "%~dp0"
python smtp_proxy.py

pause
