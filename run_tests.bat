@echo off
cd /d "%~dp0"
set PYTHON=C:\Users\16070\AppData\Local\Programs\Python\Python312\python.exe

echo.
echo ========================================
echo   Career Kit 测试套件
echo ========================================
echo.

echo [1/5] 运行单元测试...
%PYTHON% tests/test_career_kit.py
if errorlevel 1 goto :error
echo.

echo [2/5] 运行简历格式测试...
%PYTHON% tests/test_resume_formats.py
if errorlevel 1 goto :error
echo.

echo [3/5] 运行计划导入测试...
%PYTHON% tests/test_plan_import.py
if errorlevel 1 goto :error
echo.

echo [4/5] 运行 MCP 客户端测试...
%PYTHON% tests/test_mcp_client.py
if errorlevel 1 goto :error
echo.

echo [5/5] 运行 LLM 端到端测试...
%PYTHON% tests/test_llm_e2e.py
if errorlevel 1 goto :error
echo.

echo ========================================
echo   所有测试通过!
echo ========================================
goto :end

:error
echo.
echo ========================================
echo   测试失败!
echo ========================================

:end
pause
