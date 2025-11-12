import requests
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from typing import Optional, Dict, Any

class ZadarmaAPI:
    def __init__(self, key: str, secret: str):
        self.key = key
        self.secret = secret
        self.base_url = "https://api.zadarma.com"
    
    def _generate_signature(self, method: str, endpoint: str, params: Dict[str, Any] = None) -> str:
        """Generate HMAC signature according to Zadarma documentation"""
        if params is None:
            params = {}
        
        # Sort parameters alphabetically
        sorted_params = sorted(params.items())
        
        # Create parameter string (URL encoded)
        param_string = urlencode(sorted_params)
        
        # Create the data string for signature: method + endpoint + params + md5 of params
        data_string = f"{method.upper()}{endpoint}{param_string}{hashlib.md5(param_string.encode()).hexdigest()}"
        
        # Create HMAC-SHA1 signature
        signature = hmac.new(
            self.secret.encode('utf-8'),
            data_string.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()
        
        return signature
    
    def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request to Zadarma"""
        if params is None:
            params = {}
        
        # Generate signature
        signature = self._generate_signature(method, endpoint, params)
        
        # Prepare headers
        headers = {
            'Authorization': f"{self.key}:{signature}",
            'User-Agent': 'ZadarmaPythonClient/1.0'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                response = requests.post(url, headers=headers, data=params)
            else:
                raise ValueError("Unsupported HTTP method")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            return {"status": "error", "message": str(e)}
    
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        return self._make_request("/v1/info/balance/")
    
    def get_tariffs(self) -> Dict[str, Any]:
        """Get available tariffs"""
        return self._make_request("/v1/tariff/")
    
    def get_sip_numbers(self) -> Dict[str, Any]:
        """Get SIP numbers"""
        return self._make_request("/v1/sip/")

# Alternative implementation based on official documentation
class ZadarmaAPIV2:
    def __init__(self, key: str, secret: str):
        self.key = key
        self.secret = secret
        self.base_url = "https://api.zadarma.com"
    
    def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make API request using Zadarma's recommended signature method"""
        if params is None:
            params = {}
        
        # Sort and encode parameters
        sorted_params = sorted(params.items())
        param_string = urlencode(sorted_params)
        
        # Create signature data string
        data_string = f"{endpoint}{param_string}{hashlib.md5(param_string.encode()).hexdigest()}"
        
        # Generate signature
        signature = hmac.new(
            self.secret.encode('utf-8'),
            data_string.encode('utf-8'),
            hashlib.sha1
        ).hexdigest()
        
        headers = {
            'Authorization': f"{self.key}:{signature}",
            'User-Agent': 'ZadarmaPythonClient/1.0'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        print(f"Debug - URL: {url}")
        print(f"Debug - Params: {params}")
        print(f"Debug - Signature Data: {data_string}")
        print(f"Debug - Auth Header: {headers['Authorization']}")
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                response = requests.post(url, headers=headers, data=params)
            else:
                raise ValueError("Unsupported HTTP method")
            
            print(f"Debug - Response Status: {response.status_code}")
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response text: {e.response.text}")
            return {"status": "error", "message": str(e)}
    
    def get_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        return self._make_request("/v1/info/balance/")

# Test with minimal parameters
def test_with_params():
    """Test with parameters as required by some endpoints"""
    API_KEY = "b46820d6c0993ceb2258"
    API_SECRET = "your_secret_here"  # Replace with your actual secret
    
    zadarma = ZadarmaAPIV2(API_KEY, API_SECRET)
    
    # Some endpoints might require parameters even if empty
    result = zadarma.get_balance()
    print("Result:", json.dumps(result, indent=2))
    return result

# Manual signature verification
def manual_signature_test():
    """Manually create signature to verify the process"""
    key = "b46820d6c0993ceb2258"
    secret = "your_secret_here"  # Replace with your actual secret
    
    endpoint = "/v1/info/balance/"
    params = {}
    
    # Sort and encode parameters
    sorted_params = sorted(params.items())
    param_string = urlencode(sorted_params)
    
    # Create data string for signature
    data_string = f"{endpoint}{param_string}{hashlib.md5(param_string.encode()).hexdigest()}"
    
    print("Manual Signature Test:")
    print(f"Endpoint: {endpoint}")
    print(f"Params: {params}")
    print(f"Param string: {param_string}")
    print(f"Data string for signature: {data_string}")
    
    # Generate signature
    signature = hmac.new(
        secret.encode('utf-8'),
        data_string.encode('utf-8'),
        hashlib.sha1
    ).hexdigest()
    
    print(f"Generated signature: {signature}")
    print(f"Auth header would be: {key}:{signature}")
    
    # Test the request
    headers = {'Authorization': f"{key}:{signature}"}
    url = f"https://api.zadarma.com{endpoint}"
    
    response = requests.get(url, headers=headers)
    print(f"Response status: {response.status_code}")
    print(f"Response text: {response.text}")

# Check if credentials are valid using a simple approach
def check_credentials_validity():
    """Check if the API key and secret are valid"""
    print("Checking credential validity...")
    
    # Common issues to check:
    print("1. Make sure your API key is exactly as shown in Zadarma panel")
    print("2. Make sure your API secret is correct (copy-paste carefully)")
    print("3. Check if API access is enabled for your account")
    print("4. Verify there are no trailing spaces in credentials")
    
    # Test with both implementations
    API_KEY = "b46820d6c0993ceb2258"
    API_SECRET = input("Enter your API secret: ").strip()
    
    print("\nTesting with V1 implementation:")
    zadarma1 = ZadarmaAPI(API_KEY, API_SECRET)
    result1 = zadarma1.get_balance()
    print("V1 Result:", json.dumps(result1, indent=2))
    
    print("\nTesting with V2 implementation:")
    zadarma2 = ZadarmaAPIV2(API_KEY, API_SECRET)
    result2 = zadarma2.get_balance()
    print("V2 Result:", json.dumps(result2, indent=2))

if __name__ == "__main__":
    # Uncomment one of these to test:
    
    # Test with parameters
    # test_with_params()
    
    # Manual signature test
    # manual_signature_test()
    
    # Check credentials
    check_credentials_validity()