"""
Load Testing Script for Performance Optimization Verification
Tests the application under high concurrent load to verify scalability improvements
"""
import asyncio
import httpx
import time
import statistics
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Test credentials (update these)
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "password123"


async def login() -> str:
    """Login and get access token"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{API_V1}/auth/login",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        raise Exception(f"Login failed: {response.status_code}")


async def make_request(
    url: str,
    token: str,
    method: str = "GET",
    request_id: int = 0
) -> Dict:
    """Make a single API request and measure time"""
    start_time = time.time()
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            elapsed = time.time() - start_time
            
            return {
                "request_id": request_id,
                "status_code": response.status_code,
                "elapsed_time": elapsed,
                "success": response.status_code < 400
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "request_id": request_id,
            "status_code": 0,
            "elapsed_time": elapsed,
            "success": False,
            "error": str(e)
        }


async def test_concurrent_requests(
    url: str,
    token: str,
    num_requests: int = 50,
    method: str = "GET"
) -> Dict:
    """Test concurrent requests to an endpoint"""
    logger.info(f"Testing {num_requests} concurrent {method} requests to {url}")
    
    start_time = time.time()
    
    # Create all tasks
    tasks = [
        make_request(url, token, method, i)
        for i in range(num_requests)
    ]
    
    # Execute all concurrently
    results = await asyncio.gather(*tasks)
    
    total_time = time.time() - start_time
    
    # Analyze results
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    times = [r["elapsed_time"] for r in successful]
    
    return {
        "total_requests": num_requests,
        "successful": len(successful),
        "failed": len(failed),
        "total_time": total_time,
        "requests_per_second": num_requests / total_time if total_time > 0 else 0,
        "response_times": {
            "min": min(times) if times else 0,
            "max": max(times) if times else 0,
            "avg": statistics.mean(times) if times else 0,
            "median": statistics.median(times) if times else 0,
            "p95": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times) if times else 0,
            "p99": sorted(times)[int(len(times) * 0.99)] if len(times) > 100 else max(times) if times else 0
        }
    }


async def test_endpoint_performance():
    """Test performance of various endpoints"""
    logger.info("=" * 80)
    logger.info("PERFORMANCE LOAD TEST")
    logger.info("=" * 80)
    
    # Login
    logger.info("Logging in...")
    token = await login()
    logger.info("✓ Login successful")
    
    # Test scenarios
    tests = [
        {
            "name": "List Calls (Light Load)",
            "url": f"{API_V1}/calls",
            "method": "GET",
            "concurrent": 20
        },
        {
            "name": "List Calls (Medium Load)",
            "url": f"{API_V1}/calls",
            "method": "GET",
            "concurrent": 50
        },
        {
            "name": "List Calls (Heavy Load)",
            "url": f"{API_V1}/calls",
            "method": "GET",
            "concurrent": 100
        },
        {
            "name": "List Agents (Heavy Load)",
            "url": f"{API_V1}/agents",
            "method": "GET",
            "concurrent": 100
        },
        {
            "name": "Get User Profile (Heavy Load)",
            "url": f"{API_V1}/profile",
            "method": "GET",
            "concurrent": 100
        }
    ]
    
    all_results = []
    
    for test in tests:
        logger.info(f"\n{'='*80}")
        logger.info(f"TEST: {test['name']}")
        logger.info(f"{'='*80}")
        
        result = await test_concurrent_requests(
            test["url"],
            token,
            test["concurrent"],
            test["method"]
        )
        
        result["test_name"] = test["name"]
        all_results.append(result)
        
        logger.info(f"\nResults:")
        logger.info(f"  Total Requests: {result['total_requests']}")
        logger.info(f"  Successful: {result['successful']} ({result['successful']/result['total_requests']*100:.1f}%)")
        logger.info(f"  Failed: {result['failed']}")
        logger.info(f"  Total Time: {result['total_time']:.2f}s")
        logger.info(f"  Requests/sec: {result['requests_per_second']:.2f}")
        logger.info(f"\n  Response Times:")
        logger.info(f"    Min: {result['response_times']['min']:.3f}s")
        logger.info(f"    Avg: {result['response_times']['avg']:.3f}s")
        logger.info(f"    Median: {result['response_times']['median']:.3f}s")
        logger.info(f"    P95: {result['response_times']['p95']:.3f}s")
        logger.info(f"    P99: {result['response_times']['p99']:.3f}s")
        logger.info(f"    Max: {result['response_times']['max']:.3f}s")
        
        # Check if performance is acceptable
        if result['response_times']['avg'] < 1.0:
            logger.info("  ✅ PASS: Average response time < 1s")
        elif result['response_times']['avg'] < 3.0:
            logger.info("  ⚠️  WARN: Average response time 1-3s")
        else:
            logger.info("  ❌ FAIL: Average response time > 3s")
        
        # Wait between tests
        await asyncio.sleep(2)
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*80}\n")
    
    for result in all_results:
        success_rate = result['successful'] / result['total_requests'] * 100
        logger.info(f"{result['test_name']}:")
        logger.info(f"  Success Rate: {success_rate:.1f}%")
        logger.info(f"  Avg Response: {result['response_times']['avg']:.3f}s")
        logger.info(f"  Throughput: {result['requests_per_second']:.2f} req/s\n")
    
    # Overall assessment
    avg_success_rate = statistics.mean([
        r['successful'] / r['total_requests'] * 100
        for r in all_results
    ])
    avg_response_time = statistics.mean([
        r['response_times']['avg']
        for r in all_results
    ])
    
    logger.info(f"{'='*80}")
    logger.info("OVERALL PERFORMANCE")
    logger.info(f"{'='*80}")
    logger.info(f"Average Success Rate: {avg_success_rate:.1f}%")
    logger.info(f"Average Response Time: {avg_response_time:.3f}s")
    
    if avg_success_rate >= 95 and avg_response_time < 1.0:
        logger.info("\n✅ EXCELLENT: Application handles high load well!")
    elif avg_success_rate >= 90 and avg_response_time < 2.0:
        logger.info("\n✅ GOOD: Application performs well under load")
    elif avg_success_rate >= 80 and avg_response_time < 3.0:
        logger.info("\n⚠️  ACCEPTABLE: Application handles load but could be optimized")
    else:
        logger.info("\n❌ NEEDS IMPROVEMENT: Application struggles under high load")


async def test_rate_limiting():
    """Test rate limiting functionality"""
    logger.info("\n" + "=" * 80)
    logger.info("RATE LIMITING TEST")
    logger.info("=" * 80)
    
    token = await login()
    
    # Make many requests quickly to trigger rate limit
    logger.info("Sending 150 requests rapidly to test rate limiting...")
    
    results = await test_concurrent_requests(
        f"{API_V1}/calls",
        token,
        num_requests=150,
        method="GET"
    )
    
    rate_limited = [
        r for r in results
        if r.get("status_code") == 429
    ]
    
    logger.info(f"\nRate Limiting Results:")
    logger.info(f"  Total Requests: {results['total_requests']}")
    logger.info(f"  Rate Limited (429): {len(rate_limited)}")
    logger.info(f"  Successful: {results['successful']}")
    
    if len(rate_limited) > 0:
        logger.info("  ✅ PASS: Rate limiting is working")
    else:
        logger.info("  ⚠️  WARN: No rate limiting detected (might be disabled or limit too high)")


async def test_database_connection_pool():
    """Test database connection pooling under load"""
    logger.info("\n" + "=" * 80)
    logger.info("DATABASE CONNECTION POOL TEST")
    logger.info("=" * 80)
    
    token = await login()
    
    # Simulate many concurrent database queries
    logger.info("Testing 200 concurrent requests to stress database pool...")
    
    results = await test_concurrent_requests(
        f"{API_V1}/calls",
        token,
        num_requests=200,
        method="GET"
    )
    
    logger.info(f"\nDatabase Pool Stress Results:")
    logger.info(f"  Total Requests: {results['total_requests']}")
    logger.info(f"  Successful: {results['successful']}")
    logger.info(f"  Failed: {results['failed']}")
    logger.info(f"  Average Response Time: {results['response_times']['avg']:.3f}s")
    
    if results['successful'] / results['total_requests'] >= 0.95:
        logger.info("  ✅ PASS: Database connection pool handles load well")
    else:
        logger.info("  ❌ FAIL: Database connection pool exhausted or errors occurred")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("LOAD TESTING & PERFORMANCE VERIFICATION")
    print("="*80)
    print("\nThis test verifies:")
    print("1. Concurrent request handling")
    print("2. Response time under load")
    print("3. Rate limiting functionality")
    print("4. Database connection pooling")
    print("5. Overall system scalability")
    print("\nMake sure your server is running at:", BASE_URL)
    print("Update TEST_EMAIL and TEST_PASSWORD with valid credentials")
    print("="*80 + "\n")
    
    try:
        # Run all tests
        asyncio.run(test_endpoint_performance())
        asyncio.run(test_rate_limiting())
        asyncio.run(test_database_connection_pool())
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80 + "\n")
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Tests failed with error: {e}")
        import traceback
        traceback.print_exc()

