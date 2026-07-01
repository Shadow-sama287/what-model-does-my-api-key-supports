import asyncio
import sys
from checker import detect_provider, APIKeyChecker

def test_detect_provider():
    print("Testing detect_provider...")
    
    # 1. Gemini Legacy
    prov, msg = detect_provider("AIzaSySomeLettersAndNumbers_12345678")
    assert prov == "Gemini", f"Expected Gemini, got {prov}"
    print("[SUCCESS] Gemini Legacy detected")
    
    # 2. Gemini New
    prov, msg = detect_provider("AQ.Ab-SomeNewLettersAndNumbers_12345678")
    assert prov == "Gemini", f"Expected Gemini, got {prov}"
    print("[SUCCESS] Gemini New detected")
    
    # 3. Anthropic
    prov, msg = detect_provider("sk-ant-api03-1234567890abcdef")
    assert prov == "Anthropic", f"Expected Anthropic, got {prov}"
    print("[SUCCESS] Anthropic detected")
    
    # 4. Groq
    prov, msg = detect_provider("gsk_123456789012345678901234567890123456789012345678")
    assert prov == "Groq", f"Expected Groq, got {prov}"
    print("[SUCCESS] Groq detected")
    
    # 5. OpenRouter
    prov, msg = detect_provider("sk-or-v1-1234567890")
    assert prov == "OpenRouter", f"Expected OpenRouter, got {prov}"
    print("[SUCCESS] OpenRouter detected")
    
    # 6. Tavily
    prov, msg = detect_provider("tvly-1234567890abcdef")
    assert prov == "Unsupported", f"Expected Unsupported for Tavily, got {prov}"
    print("[SUCCESS] Tavily key flagged as Unsupported")
    
    # 7. OpenAI Project
    prov, msg = detect_provider("sk-proj-1234567890abcdef1234567890abcdef")
    assert prov == "OpenAI", f"Expected OpenAI for sk-proj-, got {prov}"
    print("[SUCCESS] OpenAI Project Key detected")
    
    # 8. DeepSeek (sk- with 32 char suffix, 35 chars total)
    prov, msg = detect_provider("sk-12345678901234567890123456789012")
    assert prov == "DeepSeek", f"Expected DeepSeek for 35 chars key, got {prov}"
    print("[SUCCESS] DeepSeek detected based on 35 character pattern")
    
    # 9. OpenAI User (sk- with 48 char suffix, 51 chars total)
    prov, msg = detect_provider("sk-123456789012345678901234567890123456789012345678")
    assert prov == "OpenAI", f"Expected OpenAI for 51 chars key, got {prov}"
    print("[SUCCESS] OpenAI User key detected based on 51 character pattern")
    
    print("All detection tests passed!\n")

async def test_mock_checking():
    print("Testing mock checking backend...")
    
    # Test valid mock key
    checker_free = APIKeyChecker("Gemini", "mock-gemini-free-key")
    is_valid, msg = await checker_free.check_key_validity_early()
    assert is_valid == True, f"Expected valid mock key, got {is_valid}: {msg}"
    print("[SUCCESS] Early validation succeeded for mock key")
    
    # Check free key active model (gemini-1.5-flash)
    import httpx
    async with httpx.AsyncClient() as client:
        res_flash = await checker_free.check_single_model("gemini-1.5-flash", client)
        assert res_flash.status == "Active", f"Expected Active, got {res_flash.status}"
        assert res_flash.status_code == 200
        print("[SUCCESS] Free key allows gemini-1.5-flash")
        
        # Check free key restricted model (gemini-1.5-pro)
        res_pro = await checker_free.check_single_model("gemini-1.5-pro", client)
        assert res_pro.status == "Restricted (Free Tier)", f"Expected Restricted, got {res_pro.status}"
        assert res_pro.status_code == 403
        print("[SUCCESS] Free key restricts gemini-1.5-pro")
        
        # Check free key unsupported model (1.0-pro)
        res_old = await checker_free.check_single_model("gemini-1.0-pro", client)
        assert res_old.status == "Unsupported/Inactive", f"Expected Unsupported, got {res_old.status}"
        assert res_old.status_code == 404
        print("[SUCCESS] Free key reports gemini-1.0-pro as Unsupported")

        # Test quota exhausted mock key
        checker_quota = APIKeyChecker("OpenAI", "mock-openai-quota-key")
        res_quota = await checker_quota.check_single_model("gpt-4o", client)
        assert res_quota.status == "Quota Exhausted", f"Expected Quota Exhausted, got {res_quota.status}"
        assert res_quota.status_code == 429
        print("[SUCCESS] Quota exhausted key flags 429 correctly")

    print("All mock checking tests passed!\n")

if __name__ == "__main__":
    test_detect_provider()
    asyncio.run(test_mock_checking())
    print("CONGRATULATIONS: All core tests passed successfully!")
