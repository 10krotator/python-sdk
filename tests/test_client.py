from unittest.mock import Mock, patch

import pandas as pd
import pytest
import requests

from chakra_py import Chakra


def test_client_initialization():
    """Test basic client initialization."""
    client = Chakra("access:secret:username")
    assert client.token is None
    assert isinstance(client._session, requests.Session)


@patch("requests.Session")
def test_auth_login(mock_session):
    """Test authentication login."""
    # Mock the token fetch response
    mock_response = Mock()
    mock_response.json.return_value = {"token": "DDB_test123"}
    mock_session.return_value.post.return_value = mock_response

    # Create a mock headers dictionary
    mock_session.return_value.headers = {}

    client = Chakra("access:secret:username")
    client.login()

    # Verify the token fetch request
    mock_session.return_value.post.assert_called_with(
        "https://api.chakra.dev/api/v1/servers",
        json={"accessKey": "access", "secretKey": "secret", "username": "username"},
    )

    assert client.token == "DDB_test123"
    # Verify the actual headers dictionary instead of the __getitem__ call
    assert mock_session.return_value.headers["Authorization"] == "Bearer DDB_test123"


@patch("requests.Session")
def test_query_execution(mock_session):
    """Test query execution and DataFrame conversion."""
    # Mock the token fetch response
    mock_auth_response = Mock()
    mock_auth_response.json.return_value = {"token": "DDB_test123"}

    # Mock the query response
    mock_query_response = Mock()
    mock_query_response.json.return_value = {
        "columns": ["id", "name"],
        "rows": [[1, "test"], [2, "test2"]],
    }

    mock_session.return_value.post.side_effect = [
        mock_auth_response,
        mock_query_response,
    ]

    # Initialize headers dictionary
    mock_session.return_value.headers = {}

    client = Chakra("access:secret:username")
    client.login()
    df = client.execute("SELECT * FROM test_table")

    # Verify DataFrame
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["id", "name"]
    assert len(df) == 2

    # Test authentication check
    client = Chakra("access:secret:username")  # New client without login
    with pytest.raises(ValueError, match="Authentication required"):
        client.execute("SELECT * FROM test_table")


@patch("requests.Session")
def test_data_push(mock_session):
    """Test data push functionality."""
    # Initialize headers dictionary
    mock_session.return_value.headers = {}

    # Mock responses
    mock_auth_response = Mock()
    mock_auth_response.json.return_value = {"token": "DDB_test123"}

    # Set up all mock responses in the correct order
    mock_session.return_value.post.side_effect = [
        mock_auth_response,  # For login
        Mock(status_code=200),  # For create table
        Mock(status_code=200),  # For batch insert
    ]

    # Create test DataFrame
    df = pd.DataFrame({"id": [1, 2], "name": ["test1", "test2"]})

    # Create client and login first
    client = Chakra("access:secret:username")
    client.login()  # This will consume the first mock response

    # Now test pushing data
    client.push("test_table", df)

    # Verify create table request
    create_call = mock_session.return_value.post.call_args_list[1]
    assert create_call[0][0] == "https://api.chakra.dev/api/v1/execute"
    assert "CREATE TABLE IF NOT EXISTS test_table" in create_call[1]["json"]["sql"]

    # Verify batch insert request
    insert_call = mock_session.return_value.post.call_args_list[2]
    assert insert_call[0][0] == "https://api.chakra.dev/api/v1/execute/batch"
    assert len(insert_call[1]["json"]["statements"]) == 2

    # Test dictionary input not implemented
    with pytest.raises(NotImplementedError):
        client.push("test_table", {"key": "value"})

    # Test authentication check
    client = Chakra("access:secret:username")  # New client without login
    with pytest.raises(ValueError, match="Authentication required"):
        client.push("test_table", df)
