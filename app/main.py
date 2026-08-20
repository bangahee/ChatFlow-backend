from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the ChatFlow API application."""
    return FastAPI(title="ChatFlow API")


app = create_app()
