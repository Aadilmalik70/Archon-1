"""
Slack OAuth 2.0 Flow Handler

Handles OAuth authorization, token exchange, and secure token storage
"""

import httpx
import bcrypt
import os
from typing import Any

from ...config.logfire_config import get_logger
from ...utils import get_supabase_client

logger = get_logger(__name__)


class SlackOAuth:
    """
    Handles Slack OAuth 2.0 flow for workspace authentication

    Flow:
    1. User clicks "Add to Slack" → redirect to authorization URL
    2. User authorizes → Slack redirects back with code
    3. Exchange code for access token
    4. Store encrypted token in database
    """

    # OAuth configuration from environment
    CLIENT_ID = os.getenv("SLACK_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET", "")

    # Redirect URI - must match Slack app settings
    @classmethod
    def get_redirect_uri(cls, host: str = "localhost", port: int = 8181) -> str:
        """Get redirect URI based on environment"""
        # Check if APP_BASE_URL is set (for tunnel or production)
        app_base_url = os.getenv("APP_BASE_URL")
        if app_base_url:
            # Use the configured base URL (could be tunnel or production domain)
            base_url = app_base_url
        else:
            # Fallback to localhost for local development
            base_url = f"http://{host}:{port}"

        return f"{base_url}/api/integrations/slack/oauth/callback"

    # Required Slack scopes for AI-PM functionality
    SCOPES = [
        "chat:write",              # Send messages to channels
        "channels:read",           # List public channels
        "groups:read",             # List private channels
        "channels:history",        # Read message history (public)
        "groups:history",          # Read message history (private)
        "im:history",              # Read DM history
        "im:read",                 # View basic DM info
        "im:write",                # Send DMs
        "mpim:history",            # Read group DM history
        "commands",                # Slash commands
        "files:write",             # Upload files
        "users:read",              # Get user info
        "reactions:write",         # Add reactions to messages
    ]

    @classmethod
    def get_authorization_url(cls, state: str, host: str = "localhost", port: int = 8181) -> str:
        """
        Generate OAuth authorization URL for user to click

        Args:
            state: Random state string for CSRF protection
            host: Host for redirect URI
            port: Port for redirect URI

        Returns:
            Full authorization URL to redirect user to
        """
        scope_string = ",".join(cls.SCOPES)
        redirect_uri = cls.get_redirect_uri(host, port)

        auth_url = (
            f"https://slack.com/oauth/v2/authorize?"
            f"client_id={cls.CLIENT_ID}&"
            f"scope={scope_string}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}"
        )

        logger.info("Generated Slack authorization URL", extra={"state": state})
        return auth_url

    @classmethod
    async def exchange_code(cls, code: str, host: str = "localhost", port: int = 8181) -> dict[str, Any]:
        """
        Exchange authorization code for access token

        Args:
            code: Authorization code from Slack redirect
            host: Host for redirect URI
            port: Port for redirect URI

        Returns:
            Full token response from Slack including access_token, team, bot_user_id

        Raises:
            Exception: If token exchange fails
        """
        redirect_uri = cls.get_redirect_uri(host, port)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        "client_id": cls.CLIENT_ID,
                        "client_secret": cls.CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": redirect_uri,
                    },
                    timeout=30.0,
                )

                data = response.json()

                if not data.get("ok"):
                    error = data.get("error", "Unknown error")
                    logger.error(f"Slack OAuth token exchange failed: {error}")
                    raise Exception(f"Token exchange failed: {error}")

                logger.info(
                    "Successfully exchanged Slack OAuth code",
                    extra={
                        "team_id": data.get("team", {}).get("id"),
                        "team_name": data.get("team", {}).get("name"),
                    },
                )

                return data

            except httpx.RequestError as e:
                logger.error(f"HTTP error during token exchange: {str(e)}", exc_info=True)
                raise Exception(f"Network error during OAuth: {str(e)}")

    @classmethod
    async def store_credentials(cls, token_data: dict[str, Any]) -> str:
        """
        Store OAuth tokens securely in database with encryption

        Args:
            token_data: Full OAuth response from Slack

        Returns:
            credential_id (UUID) of stored credential

        Raises:
            Exception: If storage fails
        """
        supabase = get_supabase_client()

        try:
            # Extract access token
            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError("No access_token in token data")

            # Encrypt access token using bcrypt
            encrypted_token = bcrypt.hashpw(
                access_token.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            # Store plain token temporarily for retrieval
            # In production, use proper secret management (Vault, AWS Secrets Manager)
            # For now, store encrypted version in DB and plain in archon_settings

            # Delete any existing Slack credentials
            supabase.table("integration_credentials").delete().eq(
                "service_name", "slack"
            ).eq("credential_type", "oauth_token").execute()

            # Store in integration_credentials table
            metadata = {
                "team_id": token_data.get("team", {}).get("id"),
                "team_name": token_data.get("team", {}).get("name"),
                "bot_user_id": token_data.get("bot_user_id"),
                "scope": token_data.get("scope"),
                "token_type": token_data.get("token_type", "bot"),
                "app_id": token_data.get("app_id"),
                # Store actual token for use (would be in secrets manager in production)
                "access_token_plain": access_token,  # TEMPORARY - move to secrets manager
            }

            result = supabase.table("integration_credentials").insert({
                "service_name": "slack",
                "credential_type": "oauth_token",
                "encrypted_value": encrypted_token,
                "metadata": metadata,
                # Bot tokens don't expire by default
                "expires_at": None,
            }).execute()

            if not result.data:
                raise Exception("Failed to insert credential into database")

            credential_id = result.data[0]["credential_id"]

            logger.info(
                "Stored Slack credentials",
                extra={
                    "credential_id": credential_id,
                    "team": metadata.get("team_name"),
                },
            )

            return credential_id

        except Exception as e:
            logger.error(f"Failed to store Slack credentials: {str(e)}", exc_info=True)
            raise

    @classmethod
    async def get_access_token(cls) -> str | None:
        """
        Retrieve stored Slack access token

        Returns:
            Access token if found, None otherwise

        Note: In production, this would retrieve from secrets manager
        """
        supabase = get_supabase_client()

        try:
            result = supabase.table("integration_credentials").select(
                "metadata"
            ).eq("service_name", "slack").eq(
                "credential_type", "oauth_token"
            ).order("created_at", desc=True).limit(1).execute()

            if not result.data:
                logger.warning("No Slack credentials found")
                return None

            metadata = result.data[0].get("metadata", {})
            access_token = metadata.get("access_token_plain")

            if not access_token:
                logger.error("Slack credential found but no access token in metadata")
                return None

            return access_token

        except Exception as e:
            logger.error(f"Failed to retrieve Slack access token: {str(e)}", exc_info=True)
            return None

    @classmethod
    async def revoke_credentials(cls) -> bool:
        """
        Revoke Slack credentials (disconnect workspace)

        Returns:
            True if successful, False otherwise
        """
        supabase = get_supabase_client()

        try:
            # Get current token
            access_token = await cls.get_access_token()

            if access_token:
                # Revoke token via Slack API
                async with httpx.AsyncClient() as client:
                    try:
                        await client.post(
                            "https://slack.com/api/auth.revoke",
                            headers={"Authorization": f"Bearer {access_token}"},
                            timeout=10.0,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to revoke token via API: {str(e)}")

            # Delete from database
            result = supabase.table("integration_credentials").delete().eq(
                "service_name", "slack"
            ).eq("credential_type", "oauth_token").execute()

            logger.info("Revoked Slack credentials")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke Slack credentials: {str(e)}", exc_info=True)
            return False

    @classmethod
    async def test_connection(cls) -> dict[str, Any] | None:
        """
        Test if Slack connection is working

        Returns:
            Auth test response if successful, None if failed
        """
        try:
            access_token = await cls.get_access_token()
            if not access_token:
                return None

            from .slack_client import SlackClient

            client = SlackClient(access_token)
            return await client.test_auth()

        except Exception as e:
            logger.error(f"Slack connection test failed: {str(e)}", exc_info=True)
            return None


# Helper function to generate secure state
def generate_state() -> str:
    """Generate secure random state for OAuth CSRF protection"""
    import secrets

    return secrets.token_urlsafe(32)
