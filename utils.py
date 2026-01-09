"""
Utility functions for Metrc API integration.
Includes date handling, validation, data transformation helpers.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union
import re


class DateUtils:
    """Utilities for date and time handling."""
    
    @staticmethod
    def now_iso() -> str:
        """
        Get current datetime in ISO 8601 format with UTC timezone.
        
        Returns:
            ISO 8601 formatted datetime string
        """
        return datetime.now(timezone.utc).isoformat()
    
    @staticmethod
    def to_iso(dt: Union[datetime, str], local_tz_offset: Optional[str] = None) -> str:
        """
        Convert datetime to ISO 8601 format.
        
        Args:
            dt: Datetime object or string
            local_tz_offset: Timezone offset (e.g., '-05:00' for EST)
            
        Returns:
            ISO 8601 formatted string
        """
        if isinstance(dt, str):
            return dt
        
        if dt.tzinfo is None and local_tz_offset:
            # Add timezone info if not present
            return dt.isoformat() + local_tz_offset
        
        return dt.isoformat()
    
    @staticmethod
    def from_iso(iso_string: str) -> datetime:
        """
        Parse ISO 8601 datetime string to datetime object.
        
        Args:
            iso_string: ISO 8601 formatted string
            
        Returns:
            Datetime object
        """
        return datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    
    @staticmethod
    def date_only(dt: Union[datetime, str]) -> str:
        """
        Get date only in YYYY-MM-DD format.
        
        Args:
            dt: Datetime object or string
            
        Returns:
            Date string in YYYY-MM-DD format
        """
        if isinstance(dt, str):
            return dt.split('T')[0]
        return dt.strftime('%Y-%m-%d')
    
    @staticmethod
    def days_ago(days: int) -> str:
        """
        Get ISO 8601 datetime for N days ago.
        
        Args:
            days: Number of days ago
            
        Returns:
            ISO 8601 formatted datetime string
        """
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.isoformat()
    
    @staticmethod
    def hours_ago(hours: int) -> str:
        """
        Get ISO 8601 datetime for N hours ago.
        
        Args:
            hours: Number of hours ago
            
        Returns:
            ISO 8601 formatted datetime string
        """
        dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        return dt.isoformat()
    
    @staticmethod
    def get_sync_window(hours: int = 1, buffer_minutes: int = 5) -> tuple[str, str]:
        """
        Get time window for incremental sync with buffer.
        
        Useful for scheduled jobs that sync data changes.
        
        Args:
            hours: Number of hours back to look
            buffer_minutes: Extra minutes to include (for clock drift)
            
        Returns:
            Tuple of (start_time, end_time) in ISO 8601 format
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours, minutes=buffer_minutes)
        return start.isoformat(), now.isoformat()


class ValidationUtils:
    """Utilities for data validation."""
    
    @staticmethod
    def is_valid_tag(tag: str) -> bool:
        """
        Validate Metrc tag format.
        
        Tags are typically 24-character alphanumeric strings.
        
        Args:
            tag: Tag string to validate
            
        Returns:
            True if valid tag format
        """
        if not tag:
            return False
        # Metrc tags are typically 24 characters, alphanumeric
        return bool(re.match(r'^[A-Z0-9]{24}$', tag))
    
    @staticmethod
    def is_valid_license(license_number: str) -> bool:
        """
        Validate Massachusetts license number format.
        
        MA licenses are typically formatted like: MC281234
        
        Args:
            license_number: License number to validate
            
        Returns:
            True if valid format
        """
        if not license_number:
            return False
        # MA cultivation licenses start with MC, processing with MF
        return bool(re.match(r'^M[CFRTP]\d{6}$', license_number))
    
    @staticmethod
    def validate_weight(weight: Union[int, float], allow_negative: bool = False) -> bool:
        """
        Validate weight value.
        
        Args:
            weight: Weight value
            allow_negative: Whether to allow negative weights (for adjustments)
            
        Returns:
            True if valid
        """
        if not isinstance(weight, (int, float)):
            return False
        if allow_negative:
            return True
        return weight > 0
    
    @staticmethod
    def validate_required_fields(data: Dict, required_fields: List[str]) -> tuple[bool, List[str]]:
        """
        Validate that required fields are present in data.
        
        Args:
            data: Dictionary to validate
            required_fields: List of required field names
            
        Returns:
            Tuple of (is_valid, missing_fields)
        """
        missing = [field for field in required_fields if field not in data or data[field] is None]
        return len(missing) == 0, missing


class DataTransformUtils:
    """Utilities for data transformation and formatting."""
    
    @staticmethod
    def paginate_list(items: List[Any], page_size: int = 100) -> List[List[Any]]:
        """
        Split list into pages for batch API calls.
        
        Args:
            items: List to paginate
            page_size: Items per page
            
        Returns:
            List of pages (each page is a list)
        """
        return [items[i:i + page_size] for i in range(0, len(items), page_size)]
    
    @staticmethod
    def filter_by_strain(items: List[Dict], strain_name: str) -> List[Dict]:
        """
        Filter items by strain name (case-insensitive).
        
        Args:
            items: List of items with 'StrainName' field
            strain_name: Strain name to filter by
            
        Returns:
            Filtered list
        """
        strain_lower = strain_name.lower()
        return [
            item for item in items 
            if item.get('StrainName', '').lower() == strain_lower
        ]
    
    @staticmethod
    def filter_by_location(items: List[Dict], location_name: str) -> List[Dict]:
        """
        Filter items by location name (case-insensitive).
        
        Args:
            items: List of items with 'LocationName' field
            location_name: Location name to filter by
            
        Returns:
            Filtered list
        """
        location_lower = location_name.lower()
        return [
            item for item in items 
            if item.get('LocationName', '').lower() == location_lower
        ]
    
    @staticmethod
    def extract_tags(items: List[Dict]) -> List[str]:
        """
        Extract tags/labels from list of items.
        
        Args:
            items: List of items with 'Label' or 'Tag' field
            
        Returns:
            List of tags
        """
        tags = []
        for item in items:
            tag = item.get('Label') or item.get('Tag')
            if tag:
                tags.append(tag)
        return tags
    
    @staticmethod
    def group_by_strain(items: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group items by strain.
        
        Args:
            items: List of items with 'StrainName' field
            
        Returns:
            Dictionary mapping strain names to lists of items
        """
        groups = {}
        for item in items:
            strain = item.get('StrainName', 'Unknown')
            if strain not in groups:
                groups[strain] = []
            groups[strain].append(item)
        return groups
    
    @staticmethod
    def sum_quantities(items: List[Dict], quantity_field: str = 'Quantity') -> float:
        """
        Sum quantities across items.
        
        Args:
            items: List of items with quantity field
            quantity_field: Name of quantity field
            
        Returns:
            Total quantity
        """
        return sum(item.get(quantity_field, 0) for item in items)
    
    @staticmethod
    def convert_weight(
        weight: float,
        from_unit: str,
        to_unit: str
    ) -> float:
        """
        Convert weight between units.
        
        Args:
            weight: Weight value
            from_unit: Source unit (Grams, Ounces, Pounds, Kilograms)
            to_unit: Target unit
            
        Returns:
            Converted weight
        """
        # Convert to grams first
        to_grams = {
            'Grams': 1.0,
            'Ounces': 28.3495,
            'Pounds': 453.592,
            'Kilograms': 1000.0
        }
        
        if from_unit not in to_grams or to_unit not in to_grams:
            raise ValueError(f"Unsupported unit: {from_unit} or {to_unit}")
        
        grams = weight * to_grams[from_unit]
        return grams / to_grams[to_unit]


class ErrorFormatter:
    """Utilities for formatting API errors."""
    
    @staticmethod
    def format_validation_errors(error_response: List[Dict]) -> str:
        """
        Format Metrc validation error response into readable string.
        
        Args:
            error_response: List of error objects from 400 response
            
        Returns:
            Formatted error string
        """
        if not error_response:
            return "Validation error (no details provided)"
        
        errors = []
        for error in error_response:
            row = error.get('row', '?')
            message = error.get('message', 'Unknown error')
            errors.append(f"Row {row}: {message}")
        
        return "\n".join(errors)
    
    @staticmethod
    def format_batch_results(
        total: int,
        successful: int,
        failed: int,
        errors: Optional[List[str]] = None
    ) -> str:
        """
        Format batch operation results.
        
        Args:
            total: Total items processed
            successful: Number of successful operations
            failed: Number of failed operations
            errors: List of error messages
            
        Returns:
            Formatted results string
        """
        result = f"Batch Results:\n"
        result += f"  Total: {total}\n"
        result += f"  Successful: {successful}\n"
        result += f"  Failed: {failed}\n"
        
        if errors:
            result += f"\nErrors:\n"
            for i, error in enumerate(errors, 1):
                result += f"  {i}. {error}\n"
        
        return result


class RateLimiter:
    """Helper for managing API rate limits."""
    
    def __init__(self, calls_per_minute: int = 600):
        """
        Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum calls per minute
        """
        self.calls_per_minute = calls_per_minute
        self.call_times: List[float] = []
    
    def can_make_call(self) -> bool:
        """
        Check if a call can be made without exceeding rate limit.
        
        Returns:
            True if call can be made
        """
        now = datetime.now().timestamp()
        minute_ago = now - 60
        
        # Remove calls older than 1 minute
        self.call_times = [t for t in self.call_times if t > minute_ago]
        
        return len(self.call_times) < self.calls_per_minute
    
    def record_call(self):
        """Record that a call was made."""
        self.call_times.append(datetime.now().timestamp())
    
    def wait_time(self) -> float:
        """
        Get time to wait before next call.
        
        Returns:
            Seconds to wait (0 if can make call now)
        """
        if self.can_make_call():
            return 0.0
        
        # Find oldest call time
        if not self.call_times:
            return 0.0
        
        oldest = min(self.call_times)
        now = datetime.now().timestamp()
        wait = 60 - (now - oldest)
        
        return max(0, wait)
