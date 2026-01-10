import asyncio

import httpx

BASE_URL = "http://localhost:8000/api/v1/admin/statistics"
ADMIN_TOKEN = "your_admin_token_here"  # User should replace or we assume dev env with no auth or mock

# Mocking auth header for local dev if needed, or assume we run against running server with auth disabled or valid token
# For this verification, we will assume we can get a token or use a known one.
# Since we don't have a token, we might need to login first.
# Let's try to login as admin first.


async def verify_instructor_analytics():
    async with httpx.AsyncClient() as client:
        # 1. Login to get token (Assuming there is an admin user)
        # Replacing with a hardcoded token mechanism or just assuming the user can test manually if auth fails.
        # But wait, we can't easily login without knowing creds.
        # Check if we can disable auth or if we have a test token generator.
        # Proceeding with manual check via tool if script fails.

        # Actually, let's just inspect the response structure by calling it.
        # If 401, we know endpoints exist but need auth.

        print(f"Checking GET {BASE_URL}/instructors/top")
        resp = await client.get(
            f"{BASE_URL}/instructors/top",
            params={"sort_by": "revenue", "period": "all"},
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Response:", resp.json())

        print(f"\nChecking GET {BASE_URL}/instructors/growth")
        resp = await client.get(
            f"{BASE_URL}/instructors/growth", params={"period": "month"}
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Response:", resp.json())

        # Need an instructor ID to test detail
        # If top list returns data, pick one id
        instructor_id = "00000000-0000-0000-0000-000000000000"  # Placeholder

        print(f"\nChecking GET {BASE_URL}/instructors/{instructor_id}")
        resp = await client.get(f"{BASE_URL}/instructors/{instructor_id}")
        print(f"Status: {resp.status_code}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(verify_instructor_analytics())
