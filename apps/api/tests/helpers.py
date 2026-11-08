from fastapi.testclient import TestClient


def upload(client: TestClient, name: str, data: bytes) -> dict:
    """
    Uploads a file and returns its final status.

    TestClient runs background tasks before returning the response, so the
    document has finished processing by the time this GET runs.
    """
    created = client.post("/documents", files={"file": (name, data)})
    assert created.status_code == 201, created.text
    response = client.get(f"/documents/{created.json()['id']}")
    assert response.status_code == 200
    return response.json()
