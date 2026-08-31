$ErrorActionPreference = 'Stop'

# Run from the repository root. This installs the upstream UI UX Pro Max CLI
# and asks it to create the FULL Codex skill at .agents/skills/ui-ux-pro-max.
# Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill

$repoRoot = (Get-Location).Path
Write-Host "TAGRO ECHO repo: $repoRoot"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm is required to install UI UX Pro Max CLI.'
}

npm install -g ui-ux-pro-max-cli
if ($LASTEXITCODE -ne 0) { throw 'ui-ux-pro-max-cli installation failed.' }

uipro init --ai codex
if ($LASTEXITCODE -ne 0) { throw 'UI UX Pro Max Codex initialization failed.' }

$skillRoot = Join-Path $repoRoot '.agents\skills\ui-ux-pro-max'
$skillFile = Join-Path $skillRoot 'SKILL.md'
$searchFile = Join-Path $skillRoot 'scripts\search.py'

if (-not (Test-Path $skillFile)) { throw "Full skill install incomplete: missing $skillFile" }
if (-not (Test-Path $searchFile)) { throw "Full skill install incomplete: missing $searchFile" }

Write-Host "UI UX Pro Max full Codex skill installed: $skillRoot"
