$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$projectFile = Join-Path $projectRoot 'One_life_Shot/One_life_Shot.uproject'
$editorPath = 'E:/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe'
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw 'Unreal Editor is already running. Close it before starting another instance.'
}
if (!(Test-Path -LiteralPath $editorPath) -or !(Test-Path -LiteralPath $projectFile)) {
    throw 'Unreal Editor or project file was not found.'
}
$launchArguments = @(
    ('"{0}"' -f $projectFile), '-dx11', '-nosplash', '-NoLiveCoding', '-nosound',
    '-ModelContextProtocolStartServer', '-log=LowLoadEditor.log',
    '-ExecCmds="t.MaxFPS 30,sg.ViewDistanceQuality 0,sg.AntiAliasingQuality 0,sg.ShadowQuality 0,sg.GlobalIlluminationQuality 0,sg.ReflectionQuality 0,sg.PostProcessQuality 0,sg.TextureQuality 0,sg.EffectsQuality 0,sg.FoliageQuality 0,sg.ShadingQuality 0,r.ScreenPercentage 60"'
)
$editorProcess = Start-Process -FilePath $editorPath -ArgumentList $launchArguments -WindowStyle Hidden -PassThru
try { $editorProcess.PriorityClass = 'BelowNormal' } catch { Write-Warning 'Could not lower process priority.' }
Write-Output ('Started one low-load DX11 editor. PID: {0}' -f $editorProcess.Id)
