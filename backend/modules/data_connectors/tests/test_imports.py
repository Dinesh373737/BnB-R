"""
Quick import sanity check for the Data Connectors module.

Run with:
    python -m pytest backend/modules/data_connectors/tests/test_imports.py -q
"""

def test_data_connectors_imports():
    from backend.modules.data_connectors import router, service, schemas, grid, weather  # noqa: F401
    from backend.modules.data_connectors.schemas import WeatherResponse, GridDataResponse
    from backend.modules.data_connectors.service import DataConnectorService
    from backend.modules.data_connectors.grid import GridClient
    from backend.modules.data_connectors.weather import WeatherClient

    assert DataConnectorService is not None
    assert GridClient is not None
    assert WeatherClient is not None
    assert WeatherResponse is not None
    assert GridDataResponse is not None
