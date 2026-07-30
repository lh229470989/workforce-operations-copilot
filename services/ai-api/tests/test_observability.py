def test_request_id_security_headers_and_metrics(client):
    response = client.post(
        "/chat",
        headers={
            "X-Actor-ID": "3",
            "X-Request-ID": "demo-request-123",
        },
        json={"message": "Who am I?"},
    )

    assert response.headers["X-Request-ID"] == "demo-request-123"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"

    metrics = client.get("/metrics").text
    assert 'path="/chat",status="200"' in metrics
    assert 'intent="current_user"' in metrics


def test_invalid_request_id_is_not_reflected(client):
    response = client.get(
        "/health", headers={"X-Request-ID": "<script>alert(1)</script>"}
    )

    assert response.headers["X-Request-ID"] != "<script>alert(1)</script>"
    assert len(response.headers["X-Request-ID"]) == 36
