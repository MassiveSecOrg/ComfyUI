"""Test for authentication bypass fix.

This test demonstrates that the security fix prevents the documented bypass
where an attacker could supply an arbitrary comfy-user header to impersonate
another user.
"""

import pytest
from unittest.mock import MagicMock, patch
import tempfile

import folder_paths
from app.user_manager import UserManager


@pytest.fixture
def mock_user_directory():
    """Create a temporary user directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_dir = folder_paths.get_user_directory()
        folder_paths.set_user_directory(temp_dir)
        yield temp_dir
        folder_paths.set_user_directory(original_dir)


@pytest.fixture
def user_manager_with_tokens(mock_user_directory):
    """Create a UserManager instance with authentication tokens."""
    with patch("app.user_manager.args") as mock_args:
        mock_args.multi_user = True
        manager = UserManager()
        # Add test users
        manager.users = {"alice_123": "Alice", "bob_456": "Bob"}
        # Tokens are auto-generated, but we'll set known ones for testing
        manager.user_tokens = {
            "alice_123": "alice_secret_token_xyz",
            "bob_456": "bob_secret_token_abc",
        }
        yield manager


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    request = MagicMock()
    request.headers = {}
    return request


class TestAuthenticationBypassPrevention:
    """Tests that verify the authentication bypass is fixed."""

    def test_cannot_impersonate_with_user_header_only(
        self, user_manager_with_tokens, mock_request
    ):
        """Test that providing only comfy-user header is insufficient (the original vulnerability)."""
        # Attacker tries to impersonate Alice by only providing her user_id
        mock_request.headers = {"comfy-user": "alice_123"}

        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = True
            # This should raise KeyError because no token is provided
            with pytest.raises(KeyError, match="Authentication required"):
                user_manager_with_tokens.get_request_user_id(mock_request)

    def test_cannot_impersonate_with_wrong_token(
        self, user_manager_with_tokens, mock_request
    ):
        """Test that providing wrong token fails authentication."""
        # Attacker tries to impersonate Alice with a guessed/wrong token
        mock_request.headers = {
            "comfy-user": "alice_123",
            "comfy-user-token": "wrong_token",
        }

        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = True
            # This should raise KeyError because token doesn't match
            with pytest.raises(KeyError, match="Authentication required"):
                user_manager_with_tokens.get_request_user_id(mock_request)

    def test_cannot_use_another_users_token(
        self, user_manager_with_tokens, mock_request
    ):
        """Test that using another user's token fails (token is user-specific)."""
        # Attacker tries to impersonate Alice using Bob's token
        mock_request.headers = {
            "comfy-user": "alice_123",
            "comfy-user-token": "bob_secret_token_abc",  # Bob's token
        }

        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = True
            # This should raise KeyError because token doesn't match Alice
            with pytest.raises(KeyError, match="Authentication required"):
                user_manager_with_tokens.get_request_user_id(mock_request)

    def test_valid_authentication_succeeds(
        self, user_manager_with_tokens, mock_request
    ):
        """Test that valid user_id + token combination succeeds."""
        # Alice provides her correct credentials
        mock_request.headers = {
            "comfy-user": "alice_123",
            "comfy-user-token": "alice_secret_token_xyz",
        }

        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = True
            user_id = user_manager_with_tokens.get_request_user_id(mock_request)
            assert user_id == "alice_123"

    def test_authorization_bearer_format_works(
        self, user_manager_with_tokens, mock_request
    ):
        """Test that Authorization: Bearer format also works."""
        # Alice uses Authorization header format
        mock_request.headers = {
            "Authorization": "Bearer alice_123:alice_secret_token_xyz"
        }

        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = True
            user_id = user_manager_with_tokens.get_request_user_id(mock_request)
            assert user_id == "alice_123"

    def test_single_user_mode_unchanged(self, user_manager_with_tokens, mock_request):
        """Test that single-user mode still works without authentication."""
        # In single-user mode, no authentication is required
        mock_request.headers = {}

        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = False
            # Should return "default" without requiring any headers
            user_id = user_manager_with_tokens.get_request_user_id(mock_request)
            assert user_id == "default"


class TestUserCreationReturnsToken:
    """Tests that verify new users receive their authentication token."""

    def test_add_user_returns_token_in_multi_user_mode(
        self, user_manager_with_tokens, mock_user_directory
    ):
        """Test that creating a user in multi-user mode returns the token."""
        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = True
            result = user_manager_with_tokens.add_user("Charlie")

            # Result should be a dict with user_id and token
            assert isinstance(result, dict)
            assert "user_id" in result
            assert "token" in result
            assert result["user_id"] in user_manager_with_tokens.users
            assert len(result["token"]) > 20  # Token should be reasonably long

    def test_add_user_returns_string_in_single_user_mode(self, mock_user_directory):
        """Test that creating a user in single-user mode returns just the user_id."""
        with patch("app.user_manager.args") as mock_args:
            mock_args.multi_user = False
            manager = UserManager()
            result = manager.add_user("Charlie")

            # Result should be just a string (user_id)
            assert isinstance(result, str)
            assert "Charlie" in result or "charlie" in result.lower()
