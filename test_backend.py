#!/usr/bin/env python3
"""
Test script to verify backend API connectivity for news aggregator
"""

import httpx
import asyncio
import sys
from config import API_BASE_URL, API_SUBMIT_ENDPOINT, SEND_TO_API


async def test_backend_connection():
    """Test if backend API is reachable"""
    print("=" * 60)
    print("Testing Backend API Connectivity")
    print("=" * 60)

    # Configuration check
    print(f"\n📋 Configuration:")
    print(f"   API Base URL: {API_BASE_URL}")
    print(f"   Submit Endpoint: {API_SUBMIT_ENDPOINT}")
    print(f"   Full URL: {API_BASE_URL}{API_SUBMIT_ENDPOINT}")
    print(f"   API Submission Enabled: {SEND_TO_API}")

    if not SEND_TO_API:
        print("\n⚠️  WARNING: SEND_TO_API is set to False in config.py")
        print("   The aggregator will NOT send articles to the backend.")
        return False

    # Test connection
    print(f"\n🔄 Testing connection to backend...")

    try:
        async with httpx.AsyncClient() as client:
            # Try to reach the API (this will likely return 422 for invalid data, but confirms connectivity)
            url = f"{API_BASE_URL}{API_SUBMIT_ENDPOINT}"

            # Send a minimal test payload
            test_payload = {
                "title_kz": "Test Article",
                "title_ru": "Тестовая статья",
                "description_kz": "Test description",
                "description_ru": "Тестовое описание",
                "content_text_kz": "Test content",
                "content_text_ru": "Тестовый контент",
                "source_url": "https://test.example.com/article",
                "source_name": "Test Source",
                "language": "kz",
                "category": "education",
                "keywords_matched": "тест",
                "photo_url": ""
            }

            response = await client.post(url, json=test_payload, timeout=10.0)

            print(f"   Status Code: {response.status_code}")

            if response.status_code == 201:
                print("   ✅ SUCCESS: Backend is reachable and accepted the test article")
                print("   Note: You may want to delete this test article from your backend")
                return True
            elif response.status_code == 409:
                print("   ✅ SUCCESS: Backend is reachable (test article already exists)")
                return True
            elif response.status_code == 422:
                print("   ✅ CONNECTION OK: Backend is reachable but requires valid authentication/data")
                print(f"   Response: {response.text[:200]}")
                return True
            elif response.status_code == 401 or response.status_code == 403:
                print("   ✅ CONNECTION OK: Backend is reachable but requires authentication")
                print(f"   Response: {response.text[:200]}")
                return True
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False

    except httpx.ConnectError as e:
        print(f"   ❌ CONNECTION FAILED: Cannot reach backend at {API_BASE_URL}")
        print(f"   Error: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Check if the backend is running")
        print("   2. Verify API_BASE_URL in config.py is correct")
        print("   3. Check network connectivity")
        print("   4. Ensure firewall allows the connection")
        return False

    except httpx.TimeoutException:
        print(f"   ❌ TIMEOUT: Backend did not respond within 10 seconds")
        print("   The backend might be slow or overloaded")
        return False

    except Exception as e:
        print(f"   ❌ ERROR: {type(e).__name__}: {e}")
        return False


async def check_backend_health():
    """Try to check backend health endpoint"""
    print(f"\n🏥 Checking backend health endpoint...")

    try:
        async with httpx.AsyncClient() as client:
            # Try common health check endpoints
            health_endpoints = ["/health", "/api/health", "/", "/docs"]

            for endpoint in health_endpoints:
                url = f"{API_BASE_URL}{endpoint}"
                try:
                    response = await client.get(url, timeout=5.0)
                    if response.status_code < 500:
                        print(f"   ✅ {endpoint}: {response.status_code}")
                        if endpoint == "/docs":
                            print(f"      API documentation available at: {url}")
                        return True
                except:
                    continue

            print("   ⚠️  No standard health endpoints found")
            return False

    except Exception as e:
        print(f"   ⚠️  Health check failed: {e}")
        return False


async def main():
    """Run all backend tests"""

    # Test basic connectivity
    connection_ok = await test_backend_connection()

    # Check health endpoints
    await check_backend_health()

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    if connection_ok:
        print("✅ Backend is reachable and ready to receive articles")
        print("\n📝 Next steps:")
        print("   1. Run the aggregator to fetch news")
        print("   2. Check backend logs to verify articles are being received")
        print("   3. Monitor the data/news.json file for saved articles")
    else:
        print("❌ Backend is NOT reachable")
        print("\n📝 Action required:")
        print("   1. Start the backend server (Tabys)")
        print("   2. Update API_BASE_URL in config.py if needed")
        print("   3. Run this test again")

    print()
    return 0 if connection_ok else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
