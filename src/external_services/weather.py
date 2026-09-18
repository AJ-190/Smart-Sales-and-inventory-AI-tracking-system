import httpx


async def fetch_weather_data(
    city_name: str,
    client: httpx.AsyncClient,
):
    base_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 52.52,
        "longitude": 13.41,
        "current_weather": True
    }
    
    response = await client.get(base_url, params=params)
    response.raise_for_status()
    
    return response.json()