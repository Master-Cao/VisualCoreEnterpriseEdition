@echo off
REM 清理编译产物脚本 (Windows)

echo [CLEAN] 清理编译产物...

REM 清理build目录
if exist build (
    echo [CLEAN] 删除 build\ 目录...
    rmdir /s /q build
    echo [OK] build\ 已删除
)

REM 清理dist目录中的编译产物
if exist dist (
    echo [CLEAN] 清理 dist\ 目录中的 .pyd 和 .dll 文件...
    del /q dist\*.pyd 2>nul
    del /q dist\*.dll 2>nul
    echo [OK] dist\ 已清理
)

REM 清理CMake缓存
for /r %%i in (CMakeCache.txt) do del /q "%%i" 2>nul
for /d /r %%i in (CMakeFiles) do rmdir /s /q "%%i" 2>nul
for /r %%i in (cmake_install.cmake) do del /q "%%i" 2>nul

echo [OK] 清理完成！
echo.
echo [INFO] 可以运行 build.bat 重新编译

exit /b 0

