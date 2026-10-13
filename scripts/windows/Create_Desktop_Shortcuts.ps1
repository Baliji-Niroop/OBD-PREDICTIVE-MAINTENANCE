$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$desktop = [Environment]::GetFolderPath("Desktop")
$shell = New-Object -ComObject WScript.Shell

$shortcuts = @(
    @{
        Name = "OBD-II Dashboard.lnk"
        Script = "Launch_Dashboard.bat"
        Description = "Launch the OBD-II dashboard using the existing project environment."
    },
    @{
        Name = "OBD-II Dashboard - Setup and Update.lnk"
        Script = "Setup_Update_And_Run.bat"
        Description = "Create or update the OBD-II project environment, then launch the dashboard."
    }
)

foreach ($item in $shortcuts) {
    $shortcutPath = Join-Path $desktop $item.Name
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $PSScriptRoot $item.Script
    $shortcut.WorkingDirectory = $projectRoot
    $shortcut.Description = $item.Description
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
    $shortcut.Save()
    Write-Output "Created $shortcutPath"
}
