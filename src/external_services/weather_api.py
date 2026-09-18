from src.external_services.weather import fetch_weather_data
from fastapi import APIRouter, Depends
from src.httpx_client import get_httpx_client
import httpx



router = APIRouter(prefix='/weather')
@router.get("/{city_name}")
async def get_weather_data(
    city_name: str,
    client: httpx.AsyncClient = Depends(get_httpx_client)
):
    weather_data = await fetch_weather_data(city_name, client)
    return weather_data