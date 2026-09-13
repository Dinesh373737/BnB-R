"""GridMind — weather_data table: Weather/environmental data snapshots."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime
from backend.common.database import Base


class WeatherDataRecord(Base):
    __tablename__ = "weather_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    temperature_c = Column(Float, nullable=True)
    cloud_cover_pct = Column(Float, nullable=True)
    solar_radiation_wm2 = Column(Float, nullable=True)
    wind_speed_ms = Column(Float, nullable=True)
    weather_condition = Column(String(30), default="unknown")  # WeatherCondition
    humidity_pct = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    data_source = Column(String(20), default="simulated")  # DataSourceType
