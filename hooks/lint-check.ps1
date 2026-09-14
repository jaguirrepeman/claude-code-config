# Lint informativo tras cada Edit/Write (hook PostToolUse global).
# No bloqueante: exit 0 siempre, pase lo que pase con ruff/npm.
# Corre en el cwd de la sesion de Claude Code en ese momento.

if (Test-Path "pyproject.toml") {
    Write-Output "--- ruff check . ---"
    try { ruff check . } catch { Write-Output "(ruff no disponible: $_)" }
}

if (Test-Path "package.json") {
    try {
        $pkg = Get-Content "package.json" -Raw | ConvertFrom-Json
        if ($pkg.scripts -and $pkg.scripts.lint) {
            Write-Output "--- npm run lint ---"
            try { npm run lint } catch { Write-Output "(npm run lint fallo al invocarse: $_)" }
        }
    } catch {
        Write-Output "(no se pudo leer package.json: $_)"
    }
}

exit 0
