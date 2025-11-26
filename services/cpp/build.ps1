# Visual Core Enterprise Edition C++ 模块编译脚本 (PowerShell)
param(
    [switch]$Debug,
    [switch]$CameraOnly,
    [switch]$DetectionOnly,
    [switch]$Clean,
    [int]$Jobs = $env:NUMBER_OF_PROCESSORS,
    [switch]$MinGW,
    [switch]$Help
)

# 颜色输出函数
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Header {
    param([string]$Message)
    Write-Host ""
    Write-Host "====================================" -ForegroundColor Blue
    Write-Host "  $Message" -ForegroundColor Blue
    Write-Host "====================================" -ForegroundColor Blue
    Write-Host ""
}

# 显示帮助
if ($Help) {
    Write-Host "用法: .\build.ps1 [选项]"
    Write-Host ""
    Write-Host "选项:"
    Write-Host "  -Debug              使用Debug模式编译（默认Release）"
    Write-Host "  -CameraOnly         只编译camera模块"
    Write-Host "  -DetectionOnly      只编译detection模块"
    Write-Host "  -Clean              清理后重新编译"
    Write-Host "  -Jobs <num>         使用指定数量的并行任务（默认: CPU核心数）"
    Write-Host "  -MinGW              使用MinGW编译器（默认使用Visual Studio）"
    Write-Host "  -Help               显示此帮助信息"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\build.ps1                    # 编译所有模块"
    Write-Host "  .\build.ps1 -Clean             # 清理后重新编译"
    Write-Host "  .\build.ps1 -Debug             # Debug模式编译"
    Write-Host "  .\build.ps1 -CameraOnly        # 只编译camera模块"
    Write-Host "  .\build.ps1 -MinGW             # 使用MinGW编译"
    exit 0
}

Write-Header "Visual Core C++ 模块编译 (PowerShell)"

# 设置参数
$BuildType = if ($Debug) { "Debug" } else { "Release" }
$BuildCamera = -not $DetectionOnly
$BuildDetection = -not $CameraOnly

# 检查CMake
Write-Info "检查编译环境..."
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Error "未找到CMake，请先安装CMake"
    Write-Host "下载地址: https://cmake.org/download/"
    exit 1
}
Write-Success "找到CMake: $(cmake --version | Select-Object -First 1)"

# 检查编译器
if ($MinGW) {
    Write-Info "使用MinGW编译器"
    try {
        $null = Get-Command g++ -ErrorAction Stop
        Write-Success "找到MinGW编译器: $(g++ --version | Select-Object -First 1)"
        $Generator = "MinGW Makefiles"
    }
    catch {
        Write-Error "未找到MinGW编译器，请安装MinGW-w64"
        Write-Host "下载地址: https://www.mingw-w64.org/"
        exit 1
    }
} else {
    # 检查Visual Studio
    try {
        $null = Get-Command cl -ErrorAction Stop
        Write-Success "找到Visual Studio编译器"
        $Generator = $null
    }
    catch {
        Write-Warning "未找到Visual Studio编译器"
        Write-Info "请在Developer Command Prompt中运行此脚本"
        Write-Info "或使用 -MinGW 选项"
        Write-Host ""
        Write-Host "如何打开Developer Command Prompt:" -ForegroundColor Yellow
        Write-Host "  1. 按Win键搜索 'Developer Command Prompt'" -ForegroundColor Gray
        Write-Host "  2. 选择 'Developer Command Prompt for VS 2022' (或您安装的版本)" -ForegroundColor Gray
        Write-Host "  3. 在该终端中运行此脚本" -ForegroundColor Gray
        exit 1
    }
}

# 检查Python
Write-Info "检查Python环境..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "未找到Python，请先安装Python 3"
    Write-Host "下载地址: https://www.python.org/downloads/"
    exit 1
}

$PythonVersion = python --version 2>&1 | Out-String
Write-Info "Python版本: $($PythonVersion.Trim())"

# 检查pybind11
try {
    python -c "import pybind11" 2>&1 | Out-Null
    $Pybind11Version = python -c "import pybind11; print(pybind11.__version__)" 2>&1 | Out-String
    Write-Success "pybind11版本: $($Pybind11Version.Trim())"
} catch {
    Write-Error "未找到pybind11，请安装: pip install pybind11"
    exit 1
}
Write-Host ""

# 清理
if ($Clean) {
    Write-Info "清理旧的编译文件..."
    if (Test-Path "build") {
        Remove-Item -Recurse -Force "build"
    }
    if (Test-Path "dist") {
        Remove-Item -Force "dist\*.pyd" -ErrorAction SilentlyContinue
        Remove-Item -Force "dist\*.dll" -ErrorAction SilentlyContinue
    }
    Write-Success "清理完成"
}

# 创建build目录
if (-not (Test-Path "build")) {
    New-Item -ItemType Directory -Path "build" | Out-Null
}

Push-Location "build"

try {
    # 配置CMake
    Write-Info "配置CMake..."
    $CMakeArgs = @("-DCMAKE_BUILD_TYPE=$BuildType")
    
    if (-not $BuildCamera) {
        $CMakeArgs += "-DBUILD_CAMERA_MODULE=OFF"
        Write-Warning "跳过camera模块编译"
    }
    
    if (-not $BuildDetection) {
        $CMakeArgs += "-DBUILD_DETECTION_MODULE=OFF"
        Write-Warning "跳过detection模块编译"
    }
    
    if ($Generator) {
        $CMakeArgs += "-G", $Generator
    }
    
    Write-Info "CMake参数: $($CMakeArgs -join ' ')"
    
    $CMakeArgs += ".."
    & cmake $CMakeArgs
    if ($LASTEXITCODE -ne 0) {
        throw "CMake配置失败"
    }
    Write-Success "CMake配置完成"
    Write-Host ""
    
    # 编译
    Write-Info "开始编译（使用 $Jobs 个并行任务）..."
    & cmake --build . --config $BuildType --parallel $Jobs
    if ($LASTEXITCODE -ne 0) {
        throw "编译失败"
    }
    Write-Success "编译完成"
} catch {
    Write-Error $_
    Pop-Location
    exit 1
}

Pop-Location
Write-Host ""

# 检查生成的文件
Write-Info "检查生成的模块..."

if ($BuildCamera) {
    if (Test-Path "dist\vc_camera_cpp.pyd") {
        Write-Success "vc_camera_cpp.pyd 模块已生成"
    } else {
        Write-Warning "vc_camera_cpp.pyd 模块未找到"
    }
}

if ($BuildDetection) {
    if (Test-Path "dist\vc_detection_cpp.pyd") {
        Write-Success "vc_detection_cpp.pyd 模块已生成"
    } else {
        Write-Warning "vc_detection_cpp.pyd 模块未找到"
    }
}

Write-Host ""
Write-Info "生成的文件列表:"
if (Test-Path "dist") {
    Get-ChildItem "dist\*.pyd" | ForEach-Object {
        Write-Host "  $($_.Name) - $([math]::Round($_.Length / 1KB, 2)) KB" -ForegroundColor Gray
    }
}
Write-Host ""

Write-Header "编译流程完成！"

Write-Info "输出目录: dist\"
Write-Info "构建类型: $BuildType"
Write-Host ""
Write-Info "测试模块是否可导入:"

if ($BuildCamera) {
    Write-Host "  python -c `"import sys; sys.path.insert(0, 'dist'); import vc_camera_cpp; print('camera模块导入成功')`"" -ForegroundColor Gray
}

if ($BuildDetection) {
    Write-Host "  python -c `"import sys; sys.path.insert(0, 'dist'); import vc_detection_cpp; print('detection模块导入成功')`"" -ForegroundColor Gray
}

Write-Host ""
exit 0

