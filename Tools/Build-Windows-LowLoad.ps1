$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectFile = Join-Path $projectRoot 'One_life_Shot/One_life_Shot.uproject'
$engineVersion = (Get-Content -Raw -LiteralPath $projectFile | ConvertFrom-Json).EngineAssociation
$launcherFile = Join-Path $env:ProgramData 'Epic/UnrealEngineLauncher/LauncherInstalled.dat'
$installation = (Get-Content -Raw -LiteralPath $launcherFile | ConvertFrom-Json).InstallationList |
    Where-Object { $_.ArtifactId -eq ('UE_' + $engineVersion) } | Select-Object -First 1
if (!$installation) { throw "Unreal Engine $engineVersion installation not found." }
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) { throw 'Close Unreal Editor before packaging to conserve RAM.' }
$uat = Join-Path $installation.InstallLocation 'Engine/Build/BatchFiles/RunUAT.bat'
$cookEditor = Join-Path $installation.InstallLocation 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
$archive = Join-Path $projectRoot 'One_life_Shot/Saved/Builds/OriginalGraphics_ClickFix'
$log = Join-Path $projectRoot 'One_life_Shot/Saved/WindowsClickFixBuild.log'
$errorLog = Join-Path $projectRoot 'One_life_Shot/Saved/WindowsClickFixBuild.stderr.log'
$arguments = @('BuildCookRun', ('-project="{0}"' -f $projectFile), '-noP4', '-utf8output',
    '-platform=Win64', '-clientconfig=Shipping', '-build', '-nocompileeditor', ('-unrealexe="{0}"' -f $cookEditor), '-cook', '-map=/Game/ThirdPerson/Lvl_ThirdPerson',
    '-stage', '-pak', '-archive', ('-archivedirectory="{0}"' -f $archive), '-unattended', '-noxge',
    '-ubtargs="-MaxParallelActions=1 -NoUBA"',
    '-AdditionalCookerOptions="-nullrhi -corelimit=2 -CookProcessCount=1 -ini:Engine:[DevOptions.Shaders]:NumUnusedShaderCompilingThreads=64,NumUnusedShaderCompilingThreadsDuringGame=64,ShaderCompilerCoreCountThreshold=128,PercentageUnusedShaderCompilingThreads=100 -ini:Editor:[CookSettings]:PackagesPerGC=25 -ini:Editor:[CookPlatformDataCacheSettings]:Texture2D=2,StaticMesh=2,SkeletalMesh=2,Material=2,MaterialInstanceConstant=2,SoundWave=2"')
# All paths are concrete; cmd only invokes the engine's batch entry point.
$command = ('/d /s /c ""{0}" {1}"' -f $uat, ($arguments -join ' '))
$process = Start-Process -FilePath $env:ComSpec -ArgumentList $command -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $errorLog
$buildHandle = $process.Handle
$process.PriorityClass = 'BelowNormal'
$process.ProcessorAffinity = [intptr]3
Write-Output ('UAT Win64 Shipping, one cook/shader/build worker. PID: {0}; log: {1}; archive: {2}' -f $process.Id, $log, $archive)
$owned = [Collections.Generic.HashSet[int]]::new()
[void]$owned.Add($process.Id)
while (!$process.WaitForExit(1000)) {
    # Unreal can reset inherited affinity during startup; limit only this build's descendants.
    $rows = Get-CimInstance Win32_Process -Property ProcessId,ParentProcessId
    do {
        $added = $false
        foreach ($row in $rows) {
            if ($owned.Contains([int]$row.ParentProcessId) -and $owned.Add([int]$row.ProcessId)) { $added = $true }
        }
    } while ($added)
    foreach ($buildPid in $owned) {
        $child = Get-Process -Id $buildPid -ErrorAction SilentlyContinue
        if ($child) {
            try { $child.PriorityClass = 'BelowNormal'; $child.ProcessorAffinity = [intptr]3 }
            catch { if (!$child.HasExited) { Write-Warning "Could not limit build process $buildPid" } }
        }
    }
}
$process.Refresh()
Write-Output ('UAT exit code: {0}' -f $process.ExitCode)
if ($process.ExitCode -ne 0) { throw "Windows packaging failed; see $log and $errorLog" }
$windows = Join-Path $archive 'Windows'
if (!(Test-Path -LiteralPath (Join-Path $windows 'One_life_Shot.exe'))) { throw 'Packaged executable not found.' }
Write-Output (Join-Path $windows 'One_life_Shot.exe')
