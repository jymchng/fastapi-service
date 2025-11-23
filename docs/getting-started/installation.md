# Installation

FastAPI Service is available on PyPI and can be installed using pip, pipenv, poetry, or conda.

## Requirements

- Python 3.8+
- FastAPI 0.68+

## Install with pip

```bash
pip install fastapi-service
```

## Install with pipenv

```bash
pipenv install fastapi-service
```

## Install with poetry

```bash
poetry add fastapi-service
```

## Install with conda

```bash
conda install -c conda-forge fastapi-service
```

## Development Installation

To install from source for development:

```bash
git clone https://github.com/jymchng/fastapi-service.git
cd fastapi-service
pip install -e ".[dev]"
```

## Verify Installation

Create a simple test file to verify the installation:

```python
# test_installation.py
from fastapi_service import injectable, Container

@injectable
class HelloService:
    def greet(self, name: str):
        return f"Hello, {name}!"

# Test resolution
container = Container()
service = container.resolve(HelloService)
print(service.greet("World"))
```

Run the test:

```bash
python test_installation.py
# Output: Hello, World!
```

## Next Steps

- [Quick Start](quick-start.md) - Build your first app
- [Tutorial](tutorial.md) - Comprehensive walkthrough