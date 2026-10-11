"""Automated integration tests for FastAPI RAG endpoints."""

import io
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def create_valid_test_pdf(text: str) -> io.BytesIO:
    """Helper to create a structurally valid PDF byte stream containing text."""
    stream_content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("latin-1")
    length = len(stream_content)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    obj4 = b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    obj5 = f"5 0 obj\n<< /Length {length} >>\nstream\n".encode("latin-1") + stream_content + b"\nendstream\nendobj\n"

    header = b"%PDF-1.4\n"
    pos1 = len(header)
    pos2 = pos1 + len(obj1)
    pos3 = pos2 + len(obj2)
    pos4 = pos3 + len(obj3)
    pos5 = pos4 + len(obj4)
    xref_pos = pos5 + len(obj5)

    xref = (
        f"xref\n0 6\n"
        f"0000000000 65535 f \n"
        f"{pos1:010d} 00000 n \n"
        f"{pos2:010d} 00000 n \n"
        f"{pos3:010d} 00000 n \n"
        f"{pos4:010d} 00000 n \n"
        f"{pos5:010d} 00000 n \n"
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    ).encode("latin-1")

    pdf_bytes = header + obj1 + obj2 + obj3 + obj4 + obj5 + xref
    return io.BytesIO(pdf_bytes)


def test_root_health_check():
    """Verify GET / returns 200 OK with service status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"


def test_ask_endpoint():
    """Verify POST /ask/ returns a structured answer from the LLM."""
    response = client.post("/ask/", data={"question": "What is the policy for carry-on luggage?"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0


def test_upload_and_retrieve_e2e():
    """Verify full end-to-end flow: Uploading a sample PDF and querying the knowledge base."""
    policy_text = "Kenya Airways Baggage Rule: Economy passengers are entitled to 2 free checked bags of 23kg each."
    pdf_stream = create_valid_test_pdf(policy_text)

    # 1. Login as staff to get RBAC authorization token
    staff_login = client.post(
        "/auth/login",
        json={"username_or_email": "staff", "password": "staff123"},
    )
    assert staff_login.status_code == 200
    token = staff_login.json()["access_token"]

    # 2. Test upload with staff credentials
    upload_res = client.post(
        "/upload_pdfs/",
        files={"files": ("Kenya_Airways_Policy.pdf", pdf_stream, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert "files_indexed" in upload_data

    # 3. Test asking question based on the uploaded rule
    ask_res = client.post("/ask/", data={"question": "How many free checked bags do economy passengers receive?"})
    assert ask_res.status_code == 200
    ask_data = ask_res.json()
    assert "response" in ask_data
    assert "2" in ask_data["response"] or "two" in ask_data["response"].lower()
    assert len(ask_data["sources"]) > 0
