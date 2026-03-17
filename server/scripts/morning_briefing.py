"""run by systemd timer at 07:00 -- syncs whoop then sends morning push"""
import asyncio
import httpx

BASE = "http://127.0.0.1:8000/api"


async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # sync whoop biometrics first
        try:
            await client.get(f"{BASE}/whoop/sync")
        except Exception:
            pass  # server might not have whoop connected
        # trigger morning briefing with notification
        await client.get(f"{BASE}/morning?notify=true")


if __name__ == "__main__":
    asyncio.run(main())
