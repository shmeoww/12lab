import asyncio
from sqlalchemy import update
from app.database import AsyncSessionLocal
from app.models.user import User

async def make_admin(email: str):
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(User).where(User.email == email).values(is_admin=True)
        )
        await db.commit()
        print(f"✅ {email} теперь администратор")

asyncio.run(make_admin("dr.kalinin4@gmail.com"))