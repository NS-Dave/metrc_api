"""
Supabase configuration for Metrc data warehouse.
Provides database connection and credentials management.
"""

import os
from typing import Optional


def get_supabase_password() -> str:
    """
    Get Supabase password from environment variable.
    
    Returns:
        Password string
    
    Raises:
        ValueError: If password not found
    """
    password = os.getenv('SUPABASE_PASSWORD')
    
    if not password:
        raise ValueError(
            "SUPABASE_PASSWORD environment variable not set.\n\n"
            "Set it with:\n"
            "  PowerShell: $env:SUPABASE_PASSWORD='your_password'\n"
            "  Or permanently: [System.Environment]::SetEnvironmentVariable('SUPABASE_PASSWORD', 'your_password', 'User')\n"
        )
    
    return password


def get_connection_string(password: Optional[str] = None) -> str:
    """
    Get Supabase PostgreSQL connection string.
    
    Args:
        password: Optional password override. If not provided, uses environment variable.
    
    Returns:
        PostgreSQL connection string
    """
    if password is None:
        password = get_supabase_password()
    
    return f"postgresql://postgres.kacquxbizuqgsslnubdy:{password}@aws-1-us-east-2.pooler.supabase.com:6543/postgres"


# Supabase connection details (for reference)
SUPABASE_HOST = "aws-1-us-east-2.pooler.supabase.com"
SUPABASE_PORT = 6543
SUPABASE_DATABASE = "postgres"
SUPABASE_USER = "postgres.kacquxbizuqgsslnubdy"
