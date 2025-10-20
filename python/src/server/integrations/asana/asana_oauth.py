"""
Asana OAuth 2.0 Flow Handler

Handles OAuth authorization, token exchange, and automatic refresh
CRITICAL: Asana access tokens expire after 1 hour and must be refreshed!
"""

import httpx
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from ...config.logfire_config import get_logger
from ...utils import get_supabase_client

logger = get_logger(__name__)


class AsanaOAuth:
    """
    Handles Asana OAuth 2.0 flow with automatic token refresh

    Flow:
    1. User clicks "Connect Asana" → redirect to authorization URL
    2. User authorizes → Asana redirects back with code
    3. Exchange code for access token + refresh token
    4. Store tokens with expiration tracking
    5. Auto-refresh before expiration (tokens last 1 hour)
    """

    # OAuth configuration from environment
    CLIENT_ID = os.getenv("ASANA_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("ASANA_CLIENT_SECRET", "")

    # Token endpoint
    TOKEN_URL = "https://app.asana.com/-/oauth_token"

    @classmethod
    def get_redirect_uri(cls, host: str = "localhost", port: int = 8181) -> str:
        """Get redirect URI based on environment"""
        if os.getenv("PRODUCTION") == "true":
            base_url = os.getenv("APP_BASE_URL", f"http://{host}:{port}")
        else:
            base_url = f"http://{host}:{port}"

        return f"{base_url}/api/integrations/asana/oauth/callback"

    @classmethod
    def get_authorization_url(
        cls, state: str, host: str = "localhost", port: int = 8181
    ) -> str:
        """
        Generate OAuth authorization URL

        Args:
            state: Random state string for CSRF protection
            host: Host for redirect URI
            port: Port for redirect URI

        Returns:
            Full authorization URL to redirect user to
        """
        redirect_uri = cls.get_redirect_uri(host, port)

        auth_url = (
            f"https://app.asana.com/-/oauth_authorize?"
            f"client_id={cls.CLIENT_ID}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"state={state}"
        )

        logger.info("Generated Asana authorization URL", extra={"state": state})
        return auth_url

    @classmethod
    async def exchange_code(
        cls, code: str, host: str = "localhost", port: int = 8181
    ) -> dict[str, Any]:
        """
        Exchange authorization code for access token and refresh token

        Args:
            code: Authorization code from Asana redirect
            host: Host for redirect URI
            port: Port for redirect URI

        Returns:
            Token response including:
            - access_token: Token for API calls (expires in 1 hour)
            - refresh_token: Token to get new access token
            - expires_in: Seconds until access token expires (3600)
            - token_type: "bearer"
            - data: User info

        Raises:
            Exception: If token exchange fails
        """
        redirect_uri = cls.get_redirect_uri(host, port)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    cls.TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "client_id": cls.CLIENT_ID,
                        "client_secret": cls.CLIENT_SECRET,
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                    timeout=30.0,
                )

                data = response.json()

                if response.status_code >= 400 or "error" in data:
                    error = data.get("error", "Unknown error")
                    logger.error(f"Asana OAuth token exchange failed: {error}")
                    raise Exception(f"Token exchange failed: {error}")

                logger.info(
                    "Successfully exchanged Asana OAuth code",
                    extra={
                        "user_gid": data.get("data", {}).get("gid"),
                        "expires_in": data.get("expires_in"),
                    },
                )

                return data

            except httpx.RequestError as e:
                logger.error(
                    f"HTTP error during token exchange: {str(e)}", exc_info=True
                )
                raise Exception(f"Network error during OAuth: {str(e)}")

    @classmethod
    async def refresh_access_token(cls, refresh_token: str) -> dict[str, Any]:
        """
        Refresh access token using refresh token

        CRITICAL: Asana access tokens expire after 1 hour!
        This method MUST be called before token expiration.

        Args:
            refresh_token: Refresh token from initial OAuth or previous refresh

        Returns:
            New token response with fresh access_token and refresh_token

        Raises:
            Exception: If refresh fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    cls.TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "client_id": cls.CLIENT_ID,
                        "client_secret": cls.CLIENT_SECRET,
                        "refresh_token": refresh_token,
                    },
                    timeout=30.0,
                )

                data = response.json()

                if response.status_code >= 400 or "error" in data:
                    error = data.get("error", "Unknown error")
                    logger.error(f"Asana token refresh failed: {error}")
                    raise Exception(f"Token refresh failed: {error}")

                logger.info("Successfully refreshed Asana access token")

                return data

            except httpx.RequestError as e:
                logger.error(f"HTTP error during token refresh: {str(e)}", exc_info=True)
                raise Exception(f"Network error during refresh: {str(e)}")

    @classmethod
    async def store_credentials(cls, token_data: dict[str, Any]) -> str:
        """
        Store OAuth tokens securely in database

        Args:
            token_data: Full OAuth response from Asana
                - access_token: API access token
                - refresh_token: Token to get new access token
                - expires_in: Seconds until expiration (3600)
                - data: User info

        Returns:
            credential_id (UUID) of stored credential

        Raises:
            Exception: If storage fails
        """
        supabase = get_supabase_client()

        try:
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            if not access_token or not refresh_token:
                raise ValueError("Missing access_token or refresh_token in response")

            # Calculate expiration time (with 5-minute buffer)
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in - 300
            )

            # User info from response
            user_data = token_data.get("data", {})

            # Delete any existing Asana credentials
            supabase.table("integration_credentials").delete().eq(
                "service_name", "asana"
            ).eq("credential_type", "oauth_token").execute()

            # Store in integration_credentials table
            metadata = {
                "user_gid": user_data.get("gid"),
                "user_name": user_data.get("name"),
                "user_email": user_data.get("email"),
                "token_type": token_data.get("token_type", "bearer"),
                # Store tokens for use (use secrets manager in production)
                "access_token": access_token,
                "refresh_token": refresh_token,
            }

            result = (
                supabase.table("integration_credentials")
                .insert(
                    {
                        "service_name": "asana",
                        "credential_type": "oauth_token",
                        "encrypted_value": access_token,  # Placeholder
                        "metadata": metadata,
                        "expires_at": expires_at.isoformat(),
                    }
                )
                .execute()
            )

            if not result.data:
                raise Exception("Failed to insert credential into database")

            credential_id = result.data[0]["credential_id"]

            logger.info(
                "Stored Asana credentials",
                extra={
                    "credential_id": credential_id,
                    "user": user_data.get("name"),
                    "expires_at": expires_at.isoformat(),
                },
            )

            return credential_id

        except Exception as e:
            logger.error(f"Failed to store Asana credentials: {str(e)}", exc_info=True)
            raise

    @classmethod
    async def get_access_token(cls) -> str | None:
        """
        Retrieve valid access token (auto-refreshes if expired)

        This method handles token refresh automatically:
        1. Retrieves stored token from database
        2. Checks if expired (or within 5 minutes of expiration)
        3. If expired, uses refresh token to get new access token
        4. Updates database with new tokens
        5. Returns valid access token

        Returns:
            Valid access token if found, None otherwise
        """
        supabase = get_supabase_client()

        try:
            # Get credential from database
            result = (
                supabase.table("integration_credentials")
                .select("*")
                .eq("service_name", "asana")
                .eq("credential_type", "oauth_token")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if not result.data:
                logger.warning("No Asana credentials found")
                return None

            credential = result.data[0]
            metadata = credential.get("metadata", {})
            expires_at_str = credential.get("expires_at")

            # Check if token is expired or expiring soon
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                now = datetime.now(timezone.utc)

                # If expired or expiring within 5 minutes, refresh
                if expires_at <= now:
                    logger.info("Asana token expired, refreshing...")

                    refresh_token = metadata.get("refresh_token")
                    if not refresh_token:
                        logger.error("No refresh token available")
                        return None

                    # Refresh the token
                    try:
                        new_token_data = await cls.refresh_access_token(refresh_token)

                        # Update stored credentials
                        await cls.store_credentials(new_token_data)

                        # Return new access token
                        return new_token_data.get("access_token")

                    except Exception as e:
                        logger.error(
                            f"Failed to refresh token: {str(e)}", exc_info=True
                        )
                        return None

            # Token is still valid
            access_token = metadata.get("access_token")

            if not access_token:
                logger.error("Asana credential found but no access token in metadata")
                return None

            return access_token

        except Exception as e:
            logger.error(
                f"Failed to retrieve Asana access token: {str(e)}", exc_info=True
            )
            return None

    @classmethod
    async def revoke_credentials(cls) -> bool:
        """
        Revoke Asana credentials (disconnect)

        Note: Asana doesn't provide a revoke endpoint in their API
        We just delete from our database

        Returns:
            True if successful, False otherwise
        """
        supabase = get_supabase_client()

        try:
            # Delete from database
            result = (
                supabase.table("integration_credentials")
                .delete()
                .eq("service_name", "asana")
                .eq("credential_type", "oauth_token")
                .execute()
            )

            logger.info("Revoked Asana credentials")
            return True

        except Exception as e:
            logger.error(
                f"Failed to revoke Asana credentials: {str(e)}", exc_info=True
            )
            return False

    @classmethod
    async def test_connection(cls) -> dict[str, Any] | None:
        """
        Test if Asana connection is working

        Returns:
            User info if successful, None if failed
        """
        try:
            access_token = await cls.get_access_token()
            if not access_token:
                return None

            from .asana_client import AsanaClient

            client = AsanaClient(access_token)
            return await client.test_auth()

        except Exception as e:
            logger.error(f"Asana connection test failed: {str(e)}", exc_info=True)
            return None


# Helper function to generate secure state
def generate_state() -> str:
    """Generate secure random state for OAuth CSRF protection"""
    import secrets

    return secrets.token_urlsafe(32)
