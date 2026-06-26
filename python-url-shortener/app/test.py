import  app.store.url_store
from app.models import Mapping
from datetime import datetime
import asyncio


async def a() :
    store = app.store.url_store.URLStore("sqlite+aiosqlite:///./urls.db")
    await store.initialize()
    
    date = "2026-01-01 14:00:00"
    valid_date = datetime.fromisoformat(date)
    mapping_obj = Mapping(    
        short_code="asdasdasd",
        original_url= "fffff",
        created_at= valid_date)
    #mapping = await store.create_mapping(mapping_obj)
    found   = await store.find_by_short_code("asdasdasd")
    print(found.original_url)
    #s = URLService()

asyncio.run(a())