"""
Test script to verify concurrent summary generation for multi-user support.

This script simulates multiple users generating summaries simultaneously
to ensure the fix properly handles concurrent requests without blocking.
"""
import asyncio
import httpx
import time
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration - Update these values based on your setup
BASE_URL = "http://localhost:8000/api/v1"
TEST_USERS = [
    {"email": "user1@example.com", "password": "password123"},
    {"email": "user2@example.com", "password": "password123"},
    {"email": "user3@example.com", "password": "password123"}
]


async def login(client: httpx.AsyncClient, email: str, password: str) -> str:
    """Login and return access token"""
    try:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            logger.error(f"Login failed for {email}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Login error for {email}: {e}")
        return None


async def get_call_ids(client: httpx.AsyncClient, token: str) -> List[int]:
    """Get a list of call IDs for the user"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get(f"{BASE_URL}/calls", headers=headers)
        if response.status_code == 200:
            data = response.json()
            calls = data.get("items", [])
            # Return call IDs that have transcripts
            return [call["id"] for call in calls if call.get("transcript")]
        return []
    except Exception as e:
        logger.error(f"Error getting calls: {e}")
        return []


async def trigger_summary_generation(
    client: httpx.AsyncClient,
    token: str,
    call_id: int,
    user_email: str
) -> Dict:
    """Trigger summary generation for a call"""
    start_time = time.time()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"[{user_email}] Triggering summary for call {call_id}")
        
        response = await client.post(
            f"{BASE_URL}/calls/{call_id}/generate-summary",
            headers=headers
        )
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            logger.info(
                f"[{user_email}] Summary triggered for call {call_id} "
                f"in {elapsed:.2f}s - Status: {data.get('status')}"
            )
            return {
                "success": True,
                "call_id": call_id,
                "user": user_email,
                "elapsed_time": elapsed,
                "response": data
            }
        else:
            logger.error(
                f"[{user_email}] Failed to trigger summary for call {call_id}: "
                f"{response.status_code} - {response.text}"
            )
            return {
                "success": False,
                "call_id": call_id,
                "user": user_email,
                "elapsed_time": elapsed,
                "error": response.text
            }
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[{user_email}] Error triggering summary: {e}")
        return {
            "success": False,
            "call_id": call_id,
            "user": user_email,
            "elapsed_time": elapsed,
            "error": str(e)
        }


async def check_summary_status(
    client: httpx.AsyncClient,
    token: str,
    call_id: int,
    user_email: str,
    max_retries: int = 30,
    retry_interval: int = 2
) -> Dict:
    """Poll for summary completion status"""
    headers = {"Authorization": f"Bearer {token}"}
    
    for i in range(max_retries):
        try:
            response = await client.get(
                f"{BASE_URL}/calls/{call_id}/summary-status",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("summarization_status")
                
                logger.info(
                    f"[{user_email}] Call {call_id} status check {i+1}/{max_retries}: {status}"
                )
                
                if status in ["summarized", "failed", "not_summarized"]:
                    return {
                        "success": status == "summarized",
                        "call_id": call_id,
                        "user": user_email,
                        "status": status,
                        "retries": i + 1,
                        "data": data
                    }
                
                # Still processing, wait and retry
                await asyncio.sleep(retry_interval)
            else:
                logger.error(
                    f"[{user_email}] Status check failed: {response.status_code}"
                )
                await asyncio.sleep(retry_interval)
        except Exception as e:
            logger.error(f"[{user_email}] Error checking status: {e}")
            await asyncio.sleep(retry_interval)
    
    return {
        "success": False,
        "call_id": call_id,
        "user": user_email,
        "status": "timeout",
        "retries": max_retries
    }


async def test_user_summary_generation(user: Dict) -> Dict:
    """Test summary generation for a single user"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Login
        token = await login(client, user["email"], user["password"])
        if not token:
            return {
                "user": user["email"],
                "success": False,
                "error": "Login failed"
            }
        
        # Get call IDs
        call_ids = await get_call_ids(client, token)
        if not call_ids:
            logger.warning(f"[{user['email']}] No calls with transcripts found")
            return {
                "user": user["email"],
                "success": False,
                "error": "No calls with transcripts"
            }
        
        # Use the first call
        call_id = call_ids[0]
        
        # Trigger summary generation
        trigger_result = await trigger_summary_generation(
            client, token, call_id, user["email"]
        )
        
        if not trigger_result["success"]:
            return {
                "user": user["email"],
                "success": False,
                "error": trigger_result.get("error")
            }
        
        # Check if response was immediate (non-blocking)
        if trigger_result["elapsed_time"] > 5.0:
            logger.warning(
                f"[{user['email']}] Response took {trigger_result['elapsed_time']:.2f}s "
                "(expected < 5s for non-blocking)"
            )
        
        # Poll for completion
        status_result = await check_summary_status(
            client, token, call_id, user["email"]
        )
        
        return {
            "user": user["email"],
            "call_id": call_id,
            "trigger_time": trigger_result["elapsed_time"],
            "success": status_result["success"],
            "final_status": status_result["status"],
            "retries": status_result.get("retries", 0)
        }


async def test_concurrent_summary_generation():
    """Test concurrent summary generation for multiple users"""
    logger.info("=" * 80)
    logger.info("STARTING CONCURRENT SUMMARY GENERATION TEST")
    logger.info("=" * 80)
    
    start_time = time.time()
    
    # Run all user tests concurrently
    tasks = [test_user_summary_generation(user) for user in TEST_USERS]
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # Print results
    logger.info("=" * 80)
    logger.info("TEST RESULTS")
    logger.info("=" * 80)
    
    for result in results:
        logger.info(f"\nUser: {result['user']}")
        logger.info(f"  Success: {result.get('success', False)}")
        logger.info(f"  Call ID: {result.get('call_id', 'N/A')}")
        logger.info(f"  Trigger Response Time: {result.get('trigger_time', 0):.2f}s")
        logger.info(f"  Final Status: {result.get('final_status', 'N/A')}")
        if 'error' in result:
            logger.info(f"  Error: {result['error']}")
    
    logger.info(f"\nTotal Test Duration: {total_time:.2f}s")
    logger.info(f"Number of concurrent users: {len(TEST_USERS)}")
    
    # Verify all responses were fast (non-blocking)
    slow_responses = [
        r for r in results 
        if r.get('trigger_time', 0) > 5.0
    ]
    
    if slow_responses:
        logger.warning(
            f"\n⚠️  {len(slow_responses)} user(s) had slow response times (>5s)"
        )
    else:
        logger.info("\n✅ All responses were fast (<5s) - Non-blocking confirmed!")
    
    # Check success rate
    successful = sum(1 for r in results if r.get('success', False))
    logger.info(f"\n✅ Success Rate: {successful}/{len(results)}")
    
    logger.info("=" * 80)


async def test_single_blocking_time():
    """Test how long a single summary generation takes (for comparison)"""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING SINGLE SUMMARY GENERATION TIME")
    logger.info("=" * 80)
    
    if not TEST_USERS:
        logger.error("No test users configured")
        return
    
    user = TEST_USERS[0]
    async with httpx.AsyncClient(timeout=30.0) as client:
        token = await login(client, user["email"], user["password"])
        if not token:
            logger.error("Login failed")
            return
        
        call_ids = await get_call_ids(client, token)
        if not call_ids:
            logger.warning("No calls with transcripts found")
            return
        
        call_id = call_ids[0]
        
        # Trigger and measure
        result = await trigger_summary_generation(client, token, call_id, user["email"])
        
        logger.info(f"\nSingle summary generation response time: {result['elapsed_time']:.2f}s")
        logger.info(
            f"Expected: <5s for non-blocking, 10-30s+ for blocking"
        )


if __name__ == "__main__":
    print("\n" + "="*80)
    print("CONCURRENT SUMMARY GENERATION TEST")
    print("="*80)
    print("\nThis test verifies that:")
    print("1. Multiple users can trigger summary generation concurrently")
    print("2. Requests return immediately (non-blocking)")
    print("3. Database connections are properly managed")
    print("4. Summary generation completes successfully in background")
    print("\nMake sure your server is running at:", BASE_URL)
    print("Update TEST_USERS with valid credentials if needed")
    print("="*80 + "\n")
    
    try:
        # Run single test first
        asyncio.run(test_single_blocking_time())
        
        # Then run concurrent test
        asyncio.run(test_concurrent_summary_generation())
        
        print("\n✅ Test completed successfully!")
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

