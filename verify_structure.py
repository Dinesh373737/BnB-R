#!/usr/bin/env python
"""
GridMind Module 1 Structure Verification
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

def check_file(path: Path, description: str) -> bool:
    """Check if a file exists and return True if it does."""
    exists = path.exists()
    status = "✓" if exists else "✗"
    print(f"  {status} {description}")
    if not exists:
        print(f"      Expected: {path}")
    return exists

def verify_module_structure():
    """Verify Module 1 data connectors structure."""
    print("=" * 60)
    print("Module 1: Data Connectors Structure Verification")
    print("=" * 60)
    print()
    
    base = PROJECT_ROOT / "backend" / "modules" / "data_connectors"
    
    print("Backend Module Structure:")
    print("-" * 40)
    
    required_files = [
        (base / "__init__.py", "__init__.py - Module docstring"),
        (base / "router.py", "router.py - API routes"),
        (base / "service.py", "service.py - Service layer"),
        (base / "schemas.py", "schemas.py - Pydantic schemas"),
        (base / "grid.py", "grid.py - Karnataka grid client"),
        (base / "weather.py", "weather.py - Weather client"),
        (base / "app.py", "app.py - Standalone app"),
    ]
    
    all_exist = True
    for path, desc in required_files:
        if not check_file(path, desc):
            all_exist = False
    
    print()
    print("Test Files:")
    print("-" * 40)
    
    tests_dir = base / "tests"
    test_files = [
        (tests_dir / "__init__.py", "tests/__init__.py"),
        (tests_dir / "test_imports.py", "tests/test_imports.py"),
        (tests_dir / "test_karnataka.py", "tests/test_karnataka.py"),
        (tests_dir / "test_weather.py", "tests/test_weather.py"),
    ]
    
    for path, desc in test_files:
        if not check_file(path, desc):
            all_exist = False
    
    print()
    print("Frontend Structure:")
    print("-" * 40)
    
    frontend = PROJECT_ROOT / "frontend" / "src"
    
    frontend_files = [
        (frontend / "App.tsx", "App.tsx - Main app with React Router"),
        (frontend / "App.css", "App.css - App styles"),
        (frontend / "index.css", "index.css - Design system"),
        (frontend / "main.tsx", "main.tsx - Entry point"),
        (frontend / "services" / "api.ts", "services/api.ts - API client"),
    ]
    
    for path, desc in frontend_files:
        if not check_file(path, desc):
            all_exist = False
    
    print()
    print("Frontend Pages:")
    print("-" * 40)
    
    pages = [
        ("dashboard", "DashboardPage"),
        ("karnataka", "KarnatakaGridPage"),
        ("predictions", "PredictionsPage"),
    ]
    
    for page_name, component_name in pages:
        page_dir = frontend / "pages" / page_name
        files = [
            (page_dir / f"{component_name}.tsx", f"{component_name}.tsx"),
            (page_dir / f"{component_name}.module.css", f"{component_name}.module.css"),
            (page_dir / "index.ts", f"index.ts (barrel export)"),
        ]
        for path, desc in files:
            if not check_file(path, desc):
                all_exist = False
    
    print()
    print("Data Files:")
    print("-" * 40)
    
    data_files = [
        (PROJECT_ROOT / "data_storage" / "datasets" / "historical_microgrid_data.csv", 
         "historical_microgrid_data.csv - Historical data"),
        (PROJECT_ROOT / ".env", ".env - Environment config"),
    ]
    
    for path, desc in data_files:
        if not check_file(path, desc):
            all_exist = False
    
    print()
    print("=" * 60)
    if all_exist:
        print("✓ All required files are in place!")
    else:
        print("✗ Some required files are missing")
    print("=" * 60)
    
    return all_exist


if __name__ == "__main__":
    success = verify_module_structure()
    sys.exit(0 if success else 1)
