param(
    [Parameter(Mandatory = $true)]
    # Name of a file in configsystems, e.g. S4D or S4Q
    [string]$System
)

# Copy config\systems\<System> to config\SAP_SYSTEM_INFO, the file the MCP server reads.
$config = Join-Path $PSScriptRoot "..\config"
$source = Join-Path $config "systems\$System"
$target = Join-Path $config "SAP_SYSTEM_INFO"

Copy-Item -LiteralPath $source -Destination $target -Force
Get-Content -LiteralPath $target
