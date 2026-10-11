param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$Path
)
$ErrorActionPreference = 'Stop'
Invoke-WebRequest -Uri $Url -OutFile $Path
