"""Test endpoint"""
import pytest
import requests
import json
import sys
import random
import string

# Check if a base URL was provided as a command-line argument
if len(sys.argv) > 1:
    BASE_URL = sys.argv[1]
else:
    print("Please provide the base URL as a command-line argument.")
    print("Usage: pytest test_auth.py <base_url>")
    sys.exit(1)


@pytest.fixture
def api_client():
    return requests.Session()


def random_string(length=10):
    """Generate a random string of fixed length"""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def test_successful_registration(api_client):
    # Test successful user registration
    random_email = f"{random_string()}@example.com"
    registration_data = {
        "firstName": "John",
        "lastName": "Doe",
        "email": random_email,
        "password": "securePassword123",
        "phone": "1234567890"
    }

    response = api_client.post(f"{BASE_URL}/auth/register",
                               json=registration_data)

    assert response.status_code == 201, f"Expected status code 201, but got {response.status_code}. Response: {response.text}"
    data = response.json()
    print(data)
    assert data["status"] == "success"
    assert data["message"] == "Registration successful"
    assert "accessToken" in data["data"]
    assert data["data"]["user"]["firstName"] == "John"
    assert data["data"]["user"]["lastName"] == "Doe"
    assert data["data"]["user"]["email"] == random_email

def test_missing_required_fields(api_client):
    # Test registration with missing required fields
    incomplete_data = {
        "firstName": "Jane",
        "email": f"{random_string()}@example.com",
        "password": "password123"
    }

    response = api_client.post(f"{BASE_URL}/auth/register", json=incomplete_data)

    assert response.status_code == 422, f"Expected status code 422, but got {response.status_code}. Response: {response.text}"
    data = response.json()
    assert "errors" in data
    assert any(error["field"] == "lastName" for error in data["errors"])

def test_duplicate_email(api_client):
    # Test registration with duplicate email
    random_email = f"{random_string()}@example.com"
    registration_data = {
        "firstName": "Alice",
        "lastName": "Smith",
        "email": random_email,
        "password": "alicePassword123",
        "phone": "9876543210"
    }

    # First registration should succeed
    response1 = api_client.post(f"{BASE_URL}/auth/register",
                                json=registration_data)
    assert response1.status_code == 201, f"Expected status code 201, but got {response1.status_code}. Response: {response1.text}"

    # Second registration with same email should fail
    response2 = api_client.post(f"{BASE_URL}/auth/register", json=registration_data)
    assert response2.status_code == 400, f"Expected status code 422, but got {response2.status_code}. Response: {response2.text}"
    data = response2.json()
    assert "Bad Request" in data["status"]
    assert "Registration unsuccessful" in data["message"]


def test_login_success(api_client):
    # Test successful login
    random_email = f"{random_string()}@example.com"
    password = "securePassword123"

    # First, register a new user
    registration_data = {
        "firstName": "John",
        "lastName": "Doe",
        "email": random_email,
        "password": password,
        "phone": "1234567890"
    }
    register_response = api_client.post(f"{BASE_URL}/auth/register", json=registration_data)
    assert register_response.status_code == 201, f"Failed to register user. Status: {register_response.status_code}, Response: {register_response.text}"

    # Now, try to log in
    login_data = {
        "email": random_email,
        "password": password
    }

    response = api_client.post(f"{BASE_URL}/auth/login", json=login_data)

    assert response.status_code == 200, f"Expected status code 200, but got {response.status_code}. Response: {response.text}"
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Login successful"
    assert "accessToken" in data["data"]
    print(data)
    assert data["data"]["user"]["email"] == random_email

def test_login_failure(api_client):
    # Test login with incorrect credentials
    login_data = {
        "email": f"{random_string()}@example.com",
        "password": "wrongPassword"
    }

    response = api_client.post(f"{BASE_URL}/auth/login", json=login_data)

    assert response.status_code == 401, f"Expected status code 401, but got {response.status_code}. Response: {response.text}"
    data = response.json()
    assert data["status"] == "Bad request"
    assert data["message"] == "Authentication failed"

if __name__ == "__main__":
    print(f"Running tests against {BASE_URL}")
    pytest.main([__file__]) 