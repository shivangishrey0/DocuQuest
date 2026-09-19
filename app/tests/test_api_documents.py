import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _make_pdf_bytes(lines: list[str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def test_register_and_login(client):
    email = "alice@example.com"
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "supersecret123"})
    assert resp.status_code == 201

    resp = client.post("/api/v1/auth/login", data={"username": email, "password": "supersecret123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_with_wrong_password_fails(client):
    client.post("/api/v1/auth/register", json={"email": "bob@example.com", "password": "supersecret123"})
    resp = client.post("/api/v1/auth/login", data={"username": "bob@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_upload_requires_auth(client):
    pdf_bytes = _make_pdf_bytes(["1. Test?", "A) Yes", "B) No"])
    resp = client.post("/api/v1/documents/upload", files={"file": ("q.pdf", pdf_bytes, "application/pdf")})
    assert resp.status_code == 401


def test_upload_rejects_unsupported_extension(client, auth_headers):
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("notes.txt", b"plain text content", "text/plain")},
    )
    assert resp.status_code == 415


def test_upload_process_and_retrieve_questions(client, auth_headers):
    pdf_bytes = _make_pdf_bytes(
        [
            "1. What is 2+2?",
            "A) 3",
            "B) 4",
            "C) 5",
            "D) 6",
            "",
            "2. What is the capital of Japan?",
            "A) Tokyo",
            "B) Kyoto",
        ]
    )
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 202
    document = resp.json()
    doc_id = document["id"]

    status_resp = client.get(f"/api/v1/documents/{doc_id}/status", headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "completed"

    questions_resp = client.get(f"/api/v1/documents/{doc_id}/questions", headers=auth_headers)
    assert questions_resp.status_code == 200
    questions = questions_resp.json()
    assert len(questions) == 2
    assert questions[0]["question_number"] == "1"
    assert any(o["text"] == "4" for o in questions[0]["options"])


def test_documents_are_isolated_between_users(client, auth_headers):
    pdf_bytes = _make_pdf_bytes(["1. Owner-only question?", "A) x", "B) y"])
    resp = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        files={"file": ("private.pdf", pdf_bytes, "application/pdf")},
    )
    doc_id = resp.json()["id"]

    client.post("/api/v1/auth/register", json={"email": "eve@example.com", "password": "supersecret123"})
    login = client.post("/api/v1/auth/login", data={"username": "eve@example.com", "password": "supersecret123"})
    eve_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.get(f"/api/v1/documents/{doc_id}", headers=eve_headers)
    assert resp.status_code == 404


def test_group_answer_key_matching_across_documents(client, auth_headers):
    group_resp = client.post("/api/v1/groups", headers=auth_headers, json={"name": "Set A"})
    group_id = group_resp.json()["id"]

    paper_bytes = _make_pdf_bytes(["1. Q one?", "A) x", "B) y", "", "2. Q two?", "A) x", "B) y"])
    paper_resp = client.post(
        f"/api/v1/documents/upload?group_id={group_id}",
        headers=auth_headers,
        files={"file": ("paper.pdf", paper_bytes, "application/pdf")},
    )
    assert paper_resp.status_code == 202

    key_bytes = _make_pdf_bytes(["Answer Key", "1. A", "2. B"])
    key_resp = client.post(
        f"/api/v1/documents/upload?group_id={group_id}",
        headers=auth_headers,
        files={"file": ("key.pdf", key_bytes, "application/pdf")},
    )
    assert key_resp.status_code == 202

    questions_resp = client.get(f"/api/v1/groups/{group_id}/questions", headers=auth_headers)
    questions = questions_resp.json()
    assert len(questions) == 2
    answers = {q["question_number"]: q["answer"] for q in questions}
    assert answers["1"].startswith("A")
    assert answers["2"].startswith("B")
