# Quick Start

Get up and running with FastAPI Service in under 5 minutes.

## Basic Example

Create a simple service with dependency injection:

```python
# main.py
from fastapi import FastAPI, Depends
from fastapi_service import injectable

# Define your services
@injectable
class ConfigService:
    def get_api_key(self):
        return "your-api-key"

@injectable
class WeatherService:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def get_weather(self, city: str):
        api_key = self.config.get_api_key()
        return {"city": city, "temperature": "22°C", "api_key": api_key}

# Create FastAPI app
app = FastAPI()

# Use services in endpoints
@app.get("/weather/{city}")
async def get_weather(city: str, weather: WeatherService = Depends(WeatherService)):
    return weather.get_weather(city)
```

Run the application:

```bash
uvicorn main:app --reload
```

Visit `http://localhost:8000/weather/london` to see the result.

## Adding Scope Management

Control the lifecycle of your services:

```python
from fastapi_service import injectable, Scopes

# Singleton - one instance for the entire application
@injectable(scope=Scopes.SINGLETON)
class ConfigService:
    def __init__(self):
        self.config = {"api_key": "your-api-key", "debug": True}
    
    def get(self, key: str):
        return self.config.get(key)

# Transient - new instance per request (default)
@injectable  # or @injectable(scope=Scopes.TRANSIENT)
class WeatherService:
    def __init__(self, config: ConfigService):
        self.config = config
    
    def get_weather(self, city: str):
        api_key = self.config.get("api_key")
        debug = self.config.get("debug")
        return {"city": city, "temperature": "22°C", "debug": debug}
```

## Testing Your Services

Write unit tests with dependency mocking:

```python
# test_main.py
import pytest
from fastapi_service import Container
from main import WeatherService, ConfigService

def test_weather_service():
    # Create container for test isolation
    container = Container()
    
    # Mock config service
    class MockConfig:
        def get(self, key: str):
            return "mock-api-key" if key == "api_key" else True
    
    # Register mock in container
    container._registry[ConfigService] = MockConfig()
    
    # Resolve service with mocked dependency
    weather_service = container.resolve(WeatherService)
    result = weather_service.get_weather("london")
    
    assert result["city"] == "london"
    assert result["temperature"] == "22°C"
    assert result["debug"] is True
    
    # Clean up
    container.clear()
```

## Next Steps

- [Tutorial](tutorial.md) - Build a complete application
- [Core Concepts](../concepts/dependency-injection.md) - Learn the fundamentals
- [Advanced Usage](../advanced/fastapi-integration.md) - Integration patterns