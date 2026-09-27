import asyncio
from openai import AsyncOpenAI
from youtube_qa.config import get_settings


async def main():
    settings = get_settings()

    client = AsyncOpenAI(
        api_key=settings.openai_api_key
    )

    response = await client.models.list()

    print("API connection: OK")
    print("Models available:", len(response.data))


asyncio.run(main())