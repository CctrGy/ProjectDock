"""Conectores declarativos; la detección no ejecuta código del proyecto."""
BUILTINS = {
    "git": {"executable": "git", "languages": ["*"], "recipes": {
        "git-status": ["{tool:git}", "status", "--short"],
        "git-fetch": ["{tool:git}", "fetch"],
        "git-pull": ["{tool:git}", "pull", "--ff-only"],
        "git-push": ["{tool:git}", "push"]}},
    "pytest": {"executable": "{python}", "languages": ["python"], "recipes": {"test": ["{python}", "-m", "pytest"]}},
    "ruff": {"executable": "{python}", "languages": ["python"], "recipes": {"lint": ["{python}", "-m", "ruff", "check", "."]}},
    "coverage": {"executable": "{python}", "languages": ["python"], "recipes": {"coverage": ["{python}", "-m", "coverage", "run", "-m", "pytest"]}},
    "npm": {"executable": "npm", "languages": ["javascript", "typescript"], "recipes": {"npm-test": ["{tool:npm}", "test"], "npm-build": ["{tool:npm}", "run", "build"]}},
    "dotnet": {"executable": "dotnet", "languages": ["dotnet"], "recipes": {"dotnet-build": ["{tool:dotnet}", "build"], "dotnet-test": ["{tool:dotnet}", "test"]}},
    "cargo": {"executable": "cargo", "languages": ["rust"], "recipes": {"cargo-build": ["{tool:cargo}", "build"], "cargo-test": ["{tool:cargo}", "test"]}},
    "go": {"executable": "go", "languages": ["go"], "recipes": {"go-test": ["{tool:go}", "test", "./..."]}},
    "cmake": {"executable": "cmake", "languages": ["cpp"], "recipes": {"cmake-configure": ["{tool:cmake}", "-S", ".", "-B", "build"], "cmake-build": ["{tool:cmake}", "--build", "build"]}},
    "docker": {"executable": "docker", "languages": ["*"], "recipes": {"docker-info": ["{tool:docker}", "info"]}},
    "adr": {"executable": "adr", "languages": ["*"], "recipes": {"adr": ["{tool:adr}", "list"]}},
    "gource": {"executable": "gource", "languages": ["*"], "recipes": {"gource": ["{tool:gource}", "{root}"]}},
    "github-actions": {"executable": "gh", "languages": ["*"], "recipes": {"github-actions": ["{tool:github-actions}", "run", "list"]}},
    "archify": {"executable": "", "languages": ["*"], "description": "Configura el comando de tu proveedor: no se presupone un CLI Archify.", "recipes": {}},
    "tohub": {"executable": "ToHub", "languages": ["*"], "recipes": {"git-save": ["{tool:tohub}", "--repo", "{root}", "set"]}},
}
