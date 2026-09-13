"""
Data Connectors Module — Module 1
==================================
External data ingestion for GridMind:

- Weather: Open-Meteo live API, historical CSV fallback, deterministic fallback
- Karnataka macro-grid: configurable live API, historical CSV fallback, deterministic simulation

Live-data priority chain:
1. Live Open-Meteo when ``WEATHER_LIVE_DATA_ENABLED`` is True
2. Live Karnataka API when ``KARNATAKA_GRID_API_URL`` + ``KARNATAKA_LIVE_DATA_ENABLED`` are set
3. Historical CSV from ``data_storage/datasets/historical_microgrid_data.csv``
4. Deterministic fallback simulation

Interfaces:
    GET /api/data/weather          current weather with datasource label
    GET /api/data/grid             current macro-grid state with datasource label
    GET /api/data/grid/history     persisted grid snapshots
    GET /api/data/weather/history  persisted weather snapshots

The module publishes ``data.karnataka_updated`` and ``data.weather_updated``
events when fresh data is fetched so downstream modules can react.
"""
