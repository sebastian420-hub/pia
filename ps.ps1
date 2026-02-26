# ps.ps1 - Windows Orchestrator for PIA
# Usage: ./ps.ps1 <command>

param (
    [Parameter(Mandatory=$true)]
    [string]$Action
)

switch ($Action) {
    "up" {
        docker compose up -d
    }
    "down" {
        docker compose down
    }
    "build" {
        docker compose build
    }
    "test" {
        # This runs the full orchestrator inside the container
        docker exec seismic_agent python scripts/validate_system.py
    }
    "validate" {
        # This runs just the pytest suite
        docker exec seismic_agent pytest tests/integration/test_signal_path.py -v -s
    }
    "seed-geo" {
        powershell.exe -ExecutionPolicy Bypass -File scripts/seed_geo.ps1
    }
    "logs" {
        docker logs -f seismic_agent
    }
    "clean" {
        docker compose down -v
        Get-ChildItem -Path . -Include __pycache__ -Recurse | Remove-Item -Recurse -Force
    }
    Default {
        Write-Host "Unknown action: $Action" -ForegroundColor Red
        Write-Host "Available: up, down, build, test, validate, seed-geo, logs, clean"
    }
}
