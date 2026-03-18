"""
Core Metrc API client with authentication and request handling.
Supports Massachusetts Cultivation and Processing operations.
"""
import base64
import logging
import time
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from urllib.parse import urlencode, quote_plus
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import MetrcConfig, Endpoints


class MetrcAPIError(Exception):
    """Base exception for Metrc API errors."""
    pass


class MetrcAuthenticationError(MetrcAPIError):
    """Raised when authentication fails."""
    pass


class MetrcRateLimitError(MetrcAPIError):
    """Raised when rate limit is exceeded."""
    pass


class MetrcValidationError(MetrcAPIError):
    """Raised when request validation fails."""
    pass


class MetrcClient:
    """
    Main client for interacting with Metrc API.
    
    Handles authentication, rate limiting, retries, and error handling.
    """
    
    def __init__(self, config: MetrcConfig):
        """
        Initialize Metrc API client.
        
        Args:
            config: Configuration object with API credentials and settings
        """
        self.config = config
        self.session = self._create_session()
        self._last_request_time = 0
        self._setup_logging()
        
        # Create authorization header
        self.auth_header = self._create_auth_header()
    
    def _setup_logging(self):
        """Configure logging for the client."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        if self.config.log_file:
            handler = logging.FileHandler(self.config.log_file)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry logic.
        
        Returns:
            Configured requests Session
        """
        session = requests.Session()
        
        # Configure retries for transient errors  
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        # Accept gzip encoding
        session.headers.update({'Accept-Encoding': 'gzip, deflate'})
        
        return session
    
    def _create_auth_header(self) -> str:
        """
        Create Base64 encoded authorization header.
        
        Format: Basic base64(software_api_key:user_api_key)
        
        Returns:
            Authorization header value
        """
        credentials = f"{self.config.software_api_key}:{self.config.user_api_key}"
        encoded = base64.b64encode(credentials.encode()).decode('ascii')
        return f"Basic {encoded}"
    
    def _rate_limit(self):
        """Implement rate limiting between requests."""
        if self.config.requests_per_second > 0:
            min_interval = 1.0 / self.config.requests_per_second
            elapsed = time.time() - self._last_request_time
            
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            
            self._last_request_time = time.time()
    
    def _format_datetime(self, dt: Union[datetime, str]) -> str:
        """
        Format datetime for API request (ISO 8601).
        
        Args:
            dt: Datetime object or ISO 8601 string
            
        Returns:
            ISO 8601 formatted datetime string
        """
        if isinstance(dt, str):
            return dt
        return dt.isoformat()
    
    def _encode_query_params(self, params: Dict[str, Any]) -> str:
        """
        Encode query parameters, properly handling datetime values.
        
        Args:
            params: Dictionary of query parameters
            
        Returns:
            URL-encoded query string
        """
        encoded_params = {}
        for key, value in params.items():
            if isinstance(value, datetime):
                # Format datetime and encode + as %2B
                value = self._format_datetime(value).replace('+', '%2B')
            elif isinstance(value, bool):
                value = str(value).lower()
            encoded_params[key] = value
        
        return urlencode(encoded_params, safe='%')
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict, List]] = None,
        license_number: Optional[str] = None
    ) -> Any:
        """
        Make HTTP request to Metrc API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            data: Request body data (for POST/PUT)
            license_number: License number (uses config default if not provided)
            
        Returns:
            Response data (parsed JSON)
            
        Raises:
            MetrcAPIError: For various API errors
        """
        # Rate limiting
        self._rate_limit()
        
        # Build URL
        url = self.config.get_endpoint_url(endpoint)
        
        # Add license number to params if provided
        if params is None:
            params = {}
        
        if license_number or self.config.license_number:
            params['licenseNumber'] = license_number or self.config.license_number
        
        # Build query string
        if params:
            query_string = self._encode_query_params(params)
            url = f"{url}?{query_string}"
        
        # Prepare headers
        headers = {
            'Authorization': self.auth_header,
            'Content-Type': 'application/json'
        }
        
        # Log request
        self.logger.info(f"{method} {url}")
        if data:
            self.logger.debug(f"Request data: {data}")
        
        try:
            # Make request
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                timeout=self.config.timeout
            )
            
            # Handle response
            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response content length: {len(response.content) if response.content else 0}")
            self.logger.debug(f"Response text length: {len(response.text)}")
            self.logger.debug(f"Response encoding: {response.encoding}")
            
            if response.status_code == 200:
                # Always try to parse JSON for 200 responses
                try:
                    if not response.text:
                        self.logger.error("Empty response text")
                        raise MetrcAPIError("Empty response from API")
                    
                    result = response.json()
                    self.logger.debug(f"Response parsed successfully - {len(result) if isinstance(result, list) else 'object'}")
                    return result
                except Exception as json_err:
                    self.logger.error(f"Failed to parse JSON: {json_err}")
                    self.logger.error(f"Response text (first 500): {response.text[:500]}")
                    raise MetrcAPIError(f"Failed to parse response: {json_err}")
            
            elif response.status_code == 401:
                self.logger.error(f"401 Unauthorized - Response: {response.text[:200]}")
                raise MetrcAuthenticationError(
                    "Authentication failed. Check API keys."
                )
            
            elif response.status_code == 429:
                raise MetrcRateLimitError(
                    "Rate limit exceeded. Reduce request frequency."
                )
            
            elif response.status_code == 400:
                error_msg = response.text
                try:
                    error_data = response.json()
                    if isinstance(error_data, list):
                        errors = [f"Row {e.get('row', '?')}: {e.get('message', '?')}" 
                                 for e in error_data]
                        error_msg = "\n".join(errors)
                except:
                    pass
                raise MetrcValidationError(f"Validation error:\n{error_msg}")
            
            else:
                self.logger.error(f"Status {response.status_code} - Response: {response.text[:200]}")
                raise MetrcAPIError(
                    f"API request failed with status {response.status_code}: {response.text}"
                )
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise MetrcAPIError(f"Request failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}, Status: {response.status_code if 'response' in locals() else 'unknown'}, Response: {response.text[:200] if 'response' in locals() else 'N/A'}")
            raise MetrcAPIError(f"Request failed: {e}")
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, 
            license_number: Optional[str] = None, paginate: bool = True,
            page_size: int = 20) -> Any:
        """
        Make GET request with automatic pagination support.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            license_number: License number
            paginate: Whether to automatically paginate results (default: True)
            page_size: Number of records per page (max 20 per Metrc API)
            
        Returns:
            Response data (list if paginated, original format otherwise)
        """
        # Endpoints known to support pagination
        PAGINATED_ENDPOINTS = [
            'packages/v2/active',
            'packages/v2/onhold',
            'packages/v2/inactive',
            'packages/v2/intransit',
            'packages/v2/transferred',
            'harvests/v2/active',
            'harvests/v2/onhold',
            'harvests/v2/inactive',
            'plants/v2/vegetative',
            'plants/v2/flowering',
            'plants/v2/onhold',
            'plants/v2/inactive',
            'plantbatches/v2/active',
            'plantbatches/v2/inactive'
        ]
        
        # Check if this endpoint supports pagination
        supports_pagination = any(endpoint.startswith(ep) for ep in PAGINATED_ENDPOINTS)
        
        if not paginate or not supports_pagination:
            # No pagination - single request
            return self._make_request('GET', endpoint, params=params, 
                                     license_number=license_number)
        
        # Paginate through all results
        all_results = []
        page = 1
        
        while True:
            page_params = {**(params or {}), 'pageNumber': page, 'pageSize': page_size}
            
            self.logger.info(f"Fetching page {page} (pageSize={page_size})...")
            result = self._make_request('GET', endpoint, params=page_params, 
                                       license_number=license_number)
            
            # Handle different response formats
            if isinstance(result, dict) and 'Data' in result:
                # Wrapped response format
                data = result['Data']
                if not data or len(data) == 0:
                    break
                all_results.extend(data)
                if len(data) < page_size:
                    break
            elif isinstance(result, list):
                # Direct list response
                if not result or len(result) == 0:
                    break
                all_results.extend(result)
                if len(result) < page_size:
                    break
            else:
                # Unknown format - return as-is
                return result
            
            page += 1
        
        self.logger.info(f"Pagination complete: {len(all_results)} total records from {page-1} pages")
        return all_results
    
    def post(self, endpoint: str, data: Union[Dict, List], 
             params: Optional[Dict[str, Any]] = None,
             license_number: Optional[str] = None) -> Any:
        """Make POST request."""
        return self._make_request('POST', endpoint, params=params, data=data,
                                 license_number=license_number)
    
    def put(self, endpoint: str, data: Union[Dict, List],
            params: Optional[Dict[str, Any]] = None,
            license_number: Optional[str] = None) -> Any:
        """Make PUT request."""
        return self._make_request('PUT', endpoint, params=params, data=data,
                                 license_number=license_number)
    
    def delete(self, endpoint: str, data: Union[Dict, List],
               params: Optional[Dict[str, Any]] = None,
               license_number: Optional[str] = None) -> Any:
        """Make DELETE request."""
        return self._make_request('DELETE', endpoint, params=params, data=data,
                                 license_number=license_number)
    
    # Convenience methods for common queries
    
    def get_with_last_modified(
        self,
        endpoint: str,
        last_modified_start: Union[datetime, str],
        last_modified_end: Optional[Union[datetime, str]] = None,
        license_number: Optional[str] = None
    ) -> List[Dict]:
        """
        Get resources filtered by last modified date range.
        
        Useful for incremental syncs.
        
        Args:
            endpoint: API endpoint
            last_modified_start: Start of date range
            last_modified_end: End of date range (optional)
            license_number: License number
            
        Returns:
            List of resources
        """
        params = {
            'lastModifiedStart': self._format_datetime(last_modified_start)
        }
        
        if last_modified_end:
            params['lastModifiedEnd'] = self._format_datetime(last_modified_end)
        
        return self.get(endpoint, params=params, license_number=license_number)
    
    def get_facilities(self) -> List[Dict]:
        """Get all facilities accessible to the user."""
        return self.get(Endpoints.FACILITIES)
    
    def test_connection(self) -> bool:
        """
        Test API connection and authentication.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            facilities = self.get_facilities()
            self.logger.info(f"Connection successful. Found {len(facilities)} facilities.")
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
