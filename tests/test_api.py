import pytest
from app import app, init_db

@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as atm_app
    db = tmp_path / "test.db"
    monkeypatch.setattr(atm_app, "DB_NAME", str(db))
    init_db()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def login(client):
    return client.post("/api/login", json={
        "card_number": "1234567890123456",
        "pin": "1234"
    })

def test_login_success(client):
    response = login(client)
    assert response.status_code == 200
    assert response.get_json()["success"] is True

def test_wrong_pin(client):
    response = client.post("/api/login", json={
        "card_number": "1234567890123456",
        "pin": "9999"
    })
    assert response.status_code == 401

def test_withdraw_invalid_denomination(client):
    login(client)
    response = client.post("/api/withdraw", json={"amount": 250})
    assert response.status_code == 400

def test_withdraw_insufficient_balance(client):
    login(client)
    response = client.post("/api/withdraw", json={"amount": 20000})
    assert response.status_code == 400

def test_deposit(client):
    login(client)
    response = client.post("/api/deposit", json={"amount": 5000})
    assert response.status_code == 200
    assert response.get_json()["balance"] == 15000.0
