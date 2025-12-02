import asyncio
import logging
from sqlalchemy import text
from database.connection import get_db
from database.models.database import async_engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def inspect_table():
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'farms'"))
        columns = [row[0] for row in result.fetchall()]
        logger.info(f"Columns in 'farms' table: {columns}")

if __name__ == "__main__":
    asyncio.run(inspect_table())
