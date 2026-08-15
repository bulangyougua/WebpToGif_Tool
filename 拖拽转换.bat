@echo off

if "%~1"=="" (
    echo Drag folders onto this script
    echo WebP files will be converted to GIF/PNG or split into frames
    echo Options available in the GUI window
    pause
    exit /b
)

echo [ARGS] %*
echo [DIR] %~dp0

:: 优先使用同目录下的打包 exe，无需 Python 环境
if exist "%~dp0WebP_GIF_Converter.exe" (
    echo [MODE] using bundled exe
    "%~dp0WebP_GIF_Converter.exe" %*
    goto :done
)

:: 回退：使用 python 运行脚本
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] WebP_GIF_Converter.exe not found and python not found.
    echo Install Python and add it to PATH, or place WebP_GIF_Converter.exe next to this bat.
    pause
    exit /b
)

echo [MODE] using python
python "%~dp0webp_to_gif.py" %*
goto :done

:done
if errorlevel 1 (
    echo [ERROR] Conversion failed
) else (
    echo [OK] Finished
)
pause
