#!/usr/bin/env python
"""
Quick import test for the backend to verify all modules can be loaded.
"""

import sys
sys.path.insert(0, 'backend')

def test_imports():
    print("Testing backend imports...")
    
    # Test common module imports
    from backend.common.config import settings
    print(f"✓ settings loaded (APP_MODE={settings.APP_MODE})")
    
    from backend.common.feature_flags import flags
    print(f"✓ feature_flags loaded")
    
    from backend.common.database import engine, Base, get_db_session
    print(f"✓ database loaded")
    
    from backend.common.logger import logger
    print(f"✓ logger loaded")
    
    from backend.common.events import event_bus
    print(f"✓ event_bus loaded")
    
    from backend.common.api_registry import api_registry
    print(f"✓ api_registry loaded")
    
    from backend.common.exceptions import GridMindError, DataConnectorError
    print(f"✓ exceptions loaded")
    
    # Test models
    from backend.common.models import GridStateRecord, WeatherDataRecord
    print(f"✓ models loaded")
    
    # Test schemas
    from backend.common.schemas.enums import DataSourceType, GridCondition
    from backend.common.schemas.microgrid_state import MicrogridState
    print(f"✓ schemas loaded")
    
    # Test data_connectors module
    from backend.modules.data_connectors import router, service, schemas, grid, weather
    from backend.modules.data_connectors.schemas import WeatherResponse, GridDataResponse
    from backend.modules.data_connectors.service import DataConnectorService
    from backend.modules.data_connectors.grid import GridClient
    from backend.modules.data_connectors.weather import WeatherClient
    print(f"✓ data_connectors module loaded")
    
    # Test other modules that should be available
    try:
        from backend.modules.agents.router import router as agents_router
        print(f"✓ agents module loaded")
    except Exception as e:
        print(f"⚠ agents module issue: {e}")
    
    try:
        from backend.modules.simulation.router import router as sim_router
        print(f"✓ simulation module loaded")
    except Exception as e:
        print(f"⚠ simulation module issue: {e}")
    
    try:
        from backend.modules.ml_forecasting.router import router as forecast_router
        print(f"✓ ml_forecasting module loaded")
    except Exception as e:
        print(f"⚠ ml_forecasting module issue: {e}")
    
    print()
    print("All critical imports successful!")


if __name__ == "__main__":
    test_imports()
