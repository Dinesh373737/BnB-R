# GridMind Test Runner
# Run with: powershell -ExecutionPolicy Bypass -File run_tests.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GridMind Backend Test Suite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Backend imports
Write-Host "Test 1: Backend imports..." -ForegroundColor Yellow
try {
    $pyOutput = python -c "
import sys
sys.path.insert(0, 'backend')
from backend.common.config import settings
from backend.common.feature_flags import flags
from backend.common.database import engine, Base
from backend.common.logger import logger
from backend.common.events import event_bus
from backend.common.api_registry import api_registry
from backend.common.exceptions import GridMindError, DataConnectorError
from backend.common.models import GridStateRecord, WeatherDataRecord
from backend.common.schemas.enums import DataSourceType, GridCondition
from backend.common.schemas.microgrid_state import MicrogridState
from backend.modules.data_connectors import router, service, schemas, grid, weather
from backend.modules.data_connectors.schemas import WeatherResponse, GridDataResponse
from backend.modules.data_connectors.service import DataConnectorService
from backend.modules.data_connectors.grid import GridClient
from backend.modules.data_connectors.weather import WeatherClient
print('SUCCESS')
" 2>&1
    if ($pyOutput -match "SUCCESS") {
        Write-Host "  ✓ Backend imports successful" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Backend imports failed" -ForegroundColor Red
        Write-Host $pyOutput
    }
} catch {
    Write-Host "  ✗ Backend imports failed: $_" -ForegroundColor Red
}

Write-Host ""

# Test 2: Data connectors module tests
Write-Host "Test 2: Data Connectors module tests..." -ForegroundColor Yellow
try {
    $testOutput = python backend/modules/data_connectors/run_tests.py 2>&1
    Write-Host $testOutput
    if ($testOutput -match "All Module 1 data flow tests passed") {
        Write-Host "  ✓ Data connectors tests passed" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Data connectors tests had failures" -ForegroundColor Red
    }
} catch {
    Write-Host "  ✗ Data connectors tests failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Tests complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
