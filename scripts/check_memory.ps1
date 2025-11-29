# Windows 内存诊断脚本
# PowerShell 版本

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "内存使用情况诊断脚本 (Windows)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. 系统总体内存
Write-Host "1. 系统内存使用：" -ForegroundColor Yellow
$os = Get-CimInstance -ClassName Win32_OperatingSystem
$totalMemory = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$freeMemory = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$usedMemory = [math]::Round($totalMemory - $freeMemory, 2)
$usedPercent = [math]::Round(($usedMemory / $totalMemory) * 100, 1)

Write-Host "  总内存:   ${totalMemory} GB"
Write-Host "  已使用:   ${usedMemory} GB (${usedPercent}%)"
Write-Host "  可用:     ${freeMemory} GB"
Write-Host ""

# 2. VisionCore 进程
Write-Host "2. VisionCore 相关进程：" -ForegroundColor Yellow
$processes = Get-Process python* -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*main.py*" -or $_.CommandLine -like "*app.main*"
}

if ($processes) {
    foreach ($proc in $processes) {
        $memoryMB = [math]::Round($proc.WorkingSet64 / 1MB, 2)
        $privateMB = [math]::Round($proc.PrivateMemorySize64 / 1MB, 2)
        $cpu = [math]::Round($proc.CPU, 2)
        
        Write-Host "  PID: $($proc.Id)"
        Write-Host "    工作集 (RSS):  ${memoryMB} MB"
        Write-Host "    私有内存:      ${privateMB} MB"
        Write-Host "    CPU时间:       ${cpu} 秒"
        Write-Host "    线程数:        $($proc.Threads.Count)"
    }
} else {
    Write-Host "  未找到运行中的 VisionCore 进程" -ForegroundColor Red
}
Write-Host ""

# 3. 所有 Python 进程
Write-Host "3. 所有 Python 进程：" -ForegroundColor Yellow
$allPython = Get-Process python* -ErrorAction SilentlyContinue
if ($allPython) {
    $allPython | Format-Table Id, ProcessName, 
        @{Name="Memory(MB)";Expression={[math]::Round($_.WorkingSet64/1MB,2)}},
        @{Name="CPU(s)";Expression={[math]::Round($_.CPU,2)}},
        @{Name="Threads";Expression={$_.Threads.Count}} -AutoSize
} else {
    Write-Host "  未找到 Python 进程"
}
Write-Host ""

# 4. 内存性能计数器
Write-Host "4. 内存详细信息：" -ForegroundColor Yellow
$mem = Get-Counter '\Memory\*' -ErrorAction SilentlyContinue
$mem.CounterSamples | Where-Object { 
    $_.Path -match 'Available|Committed|Cache' 
} | ForEach-Object {
    $name = $_.Path.Split('\')[-1]
    $value = [math]::Round($_.CookedValue / 1MB, 2)
    Write-Host "  ${name}: ${value} MB"
}
Write-Host ""

# 5. 页面文件使用
Write-Host "5. 页面文件（虚拟内存）：" -ForegroundColor Yellow
$pageFile = Get-CimInstance -ClassName Win32_PageFileUsage
if ($pageFile) {
    foreach ($pf in $pageFile) {
        $allocatedMB = [math]::Round($pf.AllocatedBaseSize, 2)
        $currentMB = [math]::Round($pf.CurrentUsage, 2)
        $peakMB = [math]::Round($pf.PeakUsage, 2)
        
        Write-Host "  文件: $($pf.Name)"
        Write-Host "    分配大小:  ${allocatedMB} MB"
        Write-Host "    当前使用:  ${currentMB} MB"
        Write-Host "    峰值使用:  ${peakMB} MB"
    }
} else {
    Write-Host "  未找到页面文件信息"
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "诊断完成" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "提示：" -ForegroundColor Green
Write-Host "  - Windows 没有 buff/cache 概念" -ForegroundColor Gray
Write-Host "  - 关注 '可用内存' 和进程的 '工作集'" -ForegroundColor Gray
Write-Host "  - 使用任务管理器查看详细信息" -ForegroundColor Gray

