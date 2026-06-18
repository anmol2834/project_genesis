def get_openai_client():
    from openai import AsyncOpenAI
    from app.core.config import get_config
    return AsyncOpenAI(api_key=get_config().get_openai_api_key())

__all__ = ['get_openai_client']
