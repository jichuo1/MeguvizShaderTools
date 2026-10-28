@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
set "PATH=C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin;C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
cmake -S "%~dp0.." -B "%~dp0..\build\host-windows-release" -G Ninja -DCMAKE_BUILD_TYPE=Release
if errorlevel 1 exit /b %errorlevel%
cmake --build "%~dp0..\build\host-windows-release" --target mgst --parallel 4
exit /b %errorlevel%
