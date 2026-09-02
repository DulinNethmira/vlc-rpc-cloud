from fastapi.testclient import TestClient
from main import app
from database import Base, engine
import uuid

Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_telemetry_register():
    test_id = str(uuid.uuid4())
    res = client.post("/api/telemetry/register", json={
        "installation_id": test_id,
        "app_version": "5.3.0",
        "platform": "windows"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "registered"

def test_telemetry_heartbeat():
    test_id = str(uuid.uuid4())
    # Register first
    client.post("/api/telemetry/register", json={
        "installation_id": test_id,
        "app_version": "5.3.0",
        "platform": "windows"
    })
    
    # Heartbeat
    res = client.post("/api/telemetry/heartbeat", json={
        "installation_id": test_id
    })
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    
def test_auth_register_login():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"
    
    # Register
    res = client.post("/api/auth/register", json={
        "email": email,
        "password": password
    })
    assert res.status_code == 200
    
    # Login
    res = client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert res.status_code == 200
    access_token = res.json()["access_token"]
    
    # Register device to user
    test_id = str(uuid.uuid4())
    client.post("/api/auth/register", json={
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": password,
        "installation_id": test_id
    })
    
    # Actually register in telemetry to exist
    client.post("/api/telemetry/register", json={
        "installation_id": test_id,
        "app_version": "5.3.0",
        "platform": "windows"
    })
    
    # Attach device via login
    client.post("/api/auth/login", json={
        "email": email,
        "password": password,
        "installation_id": test_id
    })
    
    # List devices
    res = client.get("/api/auth/devices", headers={"Authorization": f"Bearer {access_token}"})
    assert res.status_code == 200
    devices = res.json()
    assert len(devices) > 0
    assert any(d["id"] == test_id for d in devices)
    
    # Revoke device
    res = client.delete(f"/api/auth/devices/{test_id}", headers={"Authorization": f"Bearer {access_token}"})
    assert res.status_code == 200
    
    # List devices again
    res = client.get("/api/auth/devices", headers={"Authorization": f"Bearer {access_token}"})
    devices = res.json()
    assert not any(d["id"] == test_id for d in devices)
