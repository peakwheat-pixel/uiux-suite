param(
    [int]$ProcessId = 0,
    [string]$WindowTitleLike = "",
    [string]$OutFile = "evidence/T3.4/uia-probe.json"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$windowCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Window
)
$windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $windowCondition)

$target = $null
foreach ($window in $windows) {
    $current = $window.Current
    if ($ProcessId -gt 0 -and $current.ProcessId -ne $ProcessId) { continue }
    if ($WindowTitleLike -ne "" -and $current.Name -notlike "*$WindowTitleLike*") { continue }
    $target = $window
    break
}
if ($null -eq $target) {
    Write-Error "no matching window found (pid=$ProcessId title=$WindowTitleLike)"
    exit 3
}

function Convert-Element($element, [int]$depth) {
    $current = $element.Current
    $patterns = @()
    try {
        $patterns = $element.GetSupportedPatterns() | ForEach-Object { $_.ProgrammaticName }
    } catch { }
    $item = [ordered]@{
        name = $current.Name
        control_type = $current.ControlType.ProgrammaticName
        automation_id = $current.AutomationId
        class_name = $current.ClassName
        is_enabled = $current.IsEnabled
        is_offscreen = $current.IsOffscreen
        is_keyboard_focusable = $current.IsKeyboardFocusable
        bounds = [ordered]@{
            x = [math]::Round($current.BoundingRectangle.X, 2)
            y = [math]::Round($current.BoundingRectangle.Y, 2)
            width = [math]::Round($current.BoundingRectangle.Width, 2)
            height = [math]::Round($current.BoundingRectangle.Height, 2)
        }
        patterns = $patterns
        children = @()
    }
    if ($depth -lt 5) {
        $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
        $child = $walker.GetFirstChild($element)
        $count = 0
        while ($null -ne $child -and $count -lt 200) {
            $item.children += Convert-Element $child ($depth + 1)
            $child = $walker.GetNextSibling($child)
            $count++
        }
    }
    return $item
}

$top = Convert-Element $target 0
$flat = New-Object System.Collections.Generic.List[object]
function Flatten($node) {
    $script:flat.Add($node)
    foreach ($child in $node.children) { Flatten $child }
}
Flatten $top

$interactive = @("ControlType.Button", "ControlType.Edit", "ControlType.Hyperlink", "ControlType.CheckBox", "ControlType.RadioButton", "ControlType.ComboBox", "ControlType.ListItem", "ControlType.MenuItem", "ControlType.TabItem")
$missingNames = @($flat | Where-Object { $interactive -contains $_.control_type -and [string]::IsNullOrWhiteSpace($_.name) })
$offscreenInteractive = @($flat | Where-Object { $interactive -contains $_.control_type -and $_.is_offscreen -eq $false -and $_.bounds.width -le 0 })
$unnamedEdits = @($flat | Where-Object { $_.control_type -eq "ControlType.Edit" -and [string]::IsNullOrWhiteSpace($_.name) })

$result = [ordered]@{
    schema_version = "1.3.3"
    evidence_id = "EV-T3.4-UIA-PROBE"
    kind = "uia_tree"
    runtime_level = "NATIVE_UIA"
    generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    window = [ordered]@{
        title = $target.Current.Name
        class_name = $target.Current.ClassName
        process_id = $target.Current.ProcessId
    }
    element_count = $flat.Count
    max_depth = 5
    elements = $flat
    accessibility_summary = [ordered]@{
        interactive_count = @($flat | Where-Object { $interactive -contains $_.control_type }).Count
        missing_name_count = $missingNames.Count
        unnamed_edit_count = $unnamedEdits.Count
        zero_size_interactive_count = $offscreenInteractive.Count
    }
    producer = [ordered]@{
        script = "scripts/collect_uia_evidence.ps1"
        script_sha256 = (Get-FileHash -Algorithm SHA256 -Path $PSCommandPath).Hash.ToLower()
        host = $env:COMPUTERNAME
        os = [System.Environment]::OSVersion.VersionString
        read_only = $true
    }
    limitations = @(
        "Read-only UIA control-view snapshot; no click-through or focus-order verification.",
        "One Windows 11 Notepad (WinUI 3) window, UIA control view only; click-through, focus order and WPF/Qt/Win32-classic paths are unverified."
    )
}

$json = $result | ConvertTo-Json -Depth 20
$dir = Split-Path -Parent $OutFile
if ($dir -ne "" -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
Set-Content -Path $OutFile -Value $json -Encoding UTF8
Write-Output "wrote $OutFile elements=$($flat.Count) interactive=$($result.accessibility_summary.interactive_count) missing=$($missingNames.Count)"
