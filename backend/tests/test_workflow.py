"""End-to-end test of the complete workflow required by the project brief, plus access-control checks."""
from pathlib import Path

from app.services.seed import SAMPLE_TEXT

SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "sample_content"


def create_text(client, headers, text=SAMPLE_TEXT, title="Test post"):
    r = client.post("/api/content", json={"title": title, "text": text}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_full_workflow_admin_to_reviewer(client, auth):
    admin, creator, reviewer = auth("admin"), auth("creator"), auth("reviewer")

    # 1-3. Admin logs in, edits the organisation profile, adds a new brand rule
    org = client.put("/api/organisation", headers=admin, json={
        "name": "TechNova Solutions", "industry": "Cloud", "description": "DEMO", "brand_voice": "Professional"})
    assert org.status_code == 200
    r = client.post("/api/prohibited-words", headers=admin, json={
        "phrase": "game-changing", "suggested_replacement": "significant", "severity": "Medium", "reason": "Hype"})
    assert r.status_code == 201

    # 4-5. Creator enters content
    sub = create_text(client, creator, SAMPLE_TEXT + " This is game-changing.")
    assert sub["status"] == "draft"

    # 6-8. Analysis finds violations with severity, explanation, source rule and suggestions
    res = client.post(f"/api/content/{sub['id']}/analyze", headers=creator)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "analyzed"
    issues = data["issues"]
    assert issues
    for i in issues:
        assert i["severity"] in ("Critical", "High", "Medium", "Low")
        assert i["explanation"] and i["rule_reference"] and i["rule_snapshot"]
        assert i["suggestion"] is not None
    ref = " | ".join(i["rule_reference"] for i in issues)
    assert "Terminology" in ref and "Prohibited word" in ref and "Approved fact" in ref and "Claim" in ref
    assert any(i["category"] == "Missing information" for i in issues)       # price without T&C notice
    assert any("game-changing" in i["flagged_text"] for i in issues)         # the rule the admin just added
    sev = {i["severity"] for i in issues}
    assert "Critical" in sev and "High" in sev

    # claim needing evidence is labelled for human verification
    claim = next(i for i in issues if i["rule_type"] == "claim")
    assert claim["requires_human_verification"] is True

    # suggestions: accept one, edit one, reject one - original text is never overwritten
    term = next(i for i in issues if i["rule_type"] == "terminology" and i["flagged_text"] == "Tech Nova Cloud")
    price = next(i for i in issues if i["rule_type"] == "fact" and "₹" in i["flagged_text"])
    r1 = client.patch(f"/api/suggestions/{term['suggestion']['id']}", json={"status": "accepted"}, headers=creator)
    assert r1.status_code == 200 and r1.json()["status"] == "accepted"
    r2 = client.patch(f"/api/suggestions/{price['suggestion']['id']}", headers=creator,
                      json={"status": "accepted", "final_text": "₹999 per month (inclusive of taxes)"})
    assert r2.json()["status"] == "edited"
    r3 = client.patch(f"/api/suggestions/{claim['suggestion']['id']}", json={"status": "rejected"}, headers=creator)
    assert r3.json()["status"] == "rejected"
    manual = client.patch(f"/api/suggestions/{claim['suggestion']['id']}", json={"status": "accepted"}, headers=creator)
    assert manual.status_code == 422  # manual suggestions need the creator's own text

    preview = client.get(f"/api/content/{sub['id']}/revised-preview", headers=creator).json()
    assert "TechNova Cloud, India" in preview["revised_text"] and "₹999 per month (inclusive" in preview["revised_text"]
    after = client.get(f"/api/content/{sub['id']}", headers=creator).json()
    assert after["original_text"] == sub["original_text"] and after["revised_text"] is None

    applied = client.post(f"/api/content/{sub['id']}/apply-suggestions", headers=creator)
    assert applied.status_code == 200
    ad = applied.json()
    assert ad["original_text"] == sub["original_text"] and ad["revised_text"] and ad["status"] == "draft"

    # cannot submit until the revised text has been analysed again
    assert client.post(f"/api/content/{sub['id']}/submit", headers=creator).status_code == 409
    re_run = client.post(f"/api/content/{sub['id']}/analyze", headers=creator).json()
    assert re_run["run_count"] == 2 and len(re_run["runs"]) == 2
    assert not [i for i in re_run["issues"] if i["flagged_text"] == "Tech Nova Cloud"]  # fixed

    # 9. creator submits for review; content is then locked
    sub_r = client.post(f"/api/content/{sub['id']}/submit", headers=creator)
    assert sub_r.status_code == 200 and sub_r.json()["status"] == "submitted"
    assert client.put(f"/api/content/{sub['id']}", json={"text": "x"}, headers=creator).status_code == 409
    assert client.post(f"/api/content/{sub['id']}/analyze", headers=creator).status_code == 409

    # 10. reviewer sees it in the queue, needs a reason to reject, then requests changes
    q = client.get("/api/reviews/queue", headers=reviewer).json()
    assert [c["id"] for c in q] == [sub["id"]]
    assert client.post(f"/api/content/{sub['id']}/review", headers=reviewer,
                       json={"decision": "rejected"}).status_code == 422
    ch = client.post(f"/api/content/{sub['id']}/review", headers=reviewer,
                     json={"decision": "changes_requested", "comment": "Please verify the No. 1 claim."})
    assert ch.status_code == 200 and ch.json()["status"] == "changes_requested"

    # creator revises, re-analyses, re-submits; reviewer approves
    assert client.put(f"/api/content/{sub['id']}", headers=creator,
                      json={"text": "TechNova Cloud is a cloud platform for businesses."}).status_code == 200
    client.post(f"/api/content/{sub['id']}/analyze", headers=creator)
    assert client.post(f"/api/content/{sub['id']}/submit", headers=creator).status_code == 200
    ok = client.post(f"/api/content/{sub['id']}/review", headers=reviewer, json={"decision": "approved"})
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    reviews = ok.json()["reviews"]
    assert [r["decision"] for r in reviews] == ["changes_requested", "approved"]
    assert reviews[0]["reviewer_name"] == "Riya Reviewer" and reviews[0]["decided_at"]
    # final decisions are locked
    assert client.post(f"/api/content/{sub['id']}/review", headers=reviewer,
                       json={"decision": "rejected", "comment": "x"}).status_code == 409

    # 11. dashboards and history reflect the final status
    d = client.get("/api/dashboard", headers=creator).json()
    assert d["approved"] == 1 and d["total_submissions"] == 2  # the seeded demo draft + this one
    da = client.get("/api/dashboard", headers=admin).json()
    assert da["approved"] == 1 and da["rule_counts"]["guidelines"] >= 5 and da["users"] == 3
    hist = client.get(f"/api/content/{sub['id']}/history", headers=admin).json()
    actions = [h["action"] for h in hist]
    assert "content.analyzed" in actions and "review.approved" in actions and "content.submitted" in actions
    an = client.get("/api/analytics", headers=reviewer).json()
    assert an["review_decisions"]["approved"] == 1 and an["most_violated_rules"]
    assert client.get("/api/reviews", headers=reviewer).json()[0]["content_title"] == "Test post"
    assert client.get("/api/audit", headers=admin).status_code == 200


def test_reject_with_reason(client, auth):
    creator, reviewer = auth("creator"), auth("reviewer")
    sub = create_text(client, creator)
    client.post(f"/api/content/{sub['id']}/analyze", headers=creator)
    client.post(f"/api/content/{sub['id']}/submit", headers=creator)
    r = client.post(f"/api/content/{sub['id']}/review", headers=reviewer,
                    json={"decision": "rejected", "comment": "Contains a prohibited guarantee."})
    assert r.json()["status"] == "rejected"


def test_role_based_access_control(client, auth):
    admin, creator, reviewer = auth("admin"), auth("creator"), auth("reviewer")
    rule = {"phrase": "x", "severity": "Low"}
    # no token
    assert client.get("/api/content").status_code == 401
    assert client.get("/api/content", headers={"Authorization": "Bearer garbage"}).status_code == 401
    # only admins manage rules and users
    for h in (creator, reviewer):
        assert client.post("/api/prohibited-words", json=rule, headers=h).status_code == 403
        assert client.get("/api/users", headers=h).status_code == 403
        assert client.put("/api/organisation", headers=h, json={"name": "Hacked"}).status_code == 403
        assert client.get("/api/audit", headers=h).status_code == 403
    assert client.get("/api/guidelines", headers=creator).status_code == 200  # read-only for everyone
    # only creators upload / analyse / submit
    for h in (admin, reviewer):
        assert client.post("/api/content", json={"title": "t", "text": "x"}, headers=h).status_code == 403
    sub = create_text(client, creator)
    for h in (admin, reviewer):
        assert client.post(f"/api/content/{sub['id']}/analyze", headers=h).status_code == 403
        assert client.post(f"/api/content/{sub['id']}/submit", headers=h).status_code == 403
    client.post(f"/api/content/{sub['id']}/analyze", headers=creator)
    client.post(f"/api/content/{sub['id']}/submit", headers=creator)
    # only reviewers decide: not the admin, not the creator
    for h in (admin, creator):
        r = client.post(f"/api/content/{sub['id']}/review", headers=h, json={"decision": "approved"})
        assert r.status_code == 403
    assert client.get("/api/analytics", headers=creator).status_code == 403
    assert client.get("/api/reviews/queue", headers=creator).status_code == 403


def test_creators_only_see_their_own_content_and_cannot_review_before_submission(client, auth):
    creator, reviewer = auth("creator"), auth("reviewer")
    other = client.post("/api/users", headers=auth("admin"), json={
        "full_name": "Other Creator", "email": "other@technova.demo", "password": "Other@1234", "role": "creator"})
    assert other.status_code == 201
    oh = {"Authorization": "Bearer " + client.post("/api/auth/login", json={
        "email": "other@technova.demo", "password": "Other@1234"}).json()["access_token"]}
    sub = create_text(client, creator)
    assert client.get(f"/api/content/{sub['id']}", headers=oh).status_code == 404
    assert client.post(f"/api/content/{sub['id']}/analyze", headers=oh).status_code == 404
    assert sub["id"] not in [c["id"] for c in client.get("/api/content", headers=oh).json()]
    assert sub["id"] in [c["id"] for c in client.get("/api/content", headers=reviewer).json()]
    # reviewer cannot decide on a draft
    r = client.post(f"/api/content/{sub['id']}/review", headers=reviewer, json={"decision": "approved"})
    assert r.status_code == 409


def test_auth_and_registration(client):
    bad = client.post("/api/auth/login", json={"email": "creator@technova.demo", "password": "wrong"})
    assert bad.status_code == 401
    orgs = client.get("/api/organisations/public").json()
    assert orgs[0]["name"] == "TechNova Solutions"
    reg = client.post("/api/auth/register", json={"full_name": "New Person", "email": "new@x.com",
                                                  "password": "Password1", "organisation_id": orgs[0]["id"]})
    assert reg.status_code == 201 and reg.json()["user"]["role"] == "creator"  # never admin
    dup = client.post("/api/auth/register", json={"full_name": "New Person", "email": "NEW@x.com",
                                                  "password": "Password1", "organisation_id": orgs[0]["id"]})
    assert dup.status_code == 400
    weak = client.post("/api/auth/register", json={"full_name": "Weak", "email": "w@x.com",
                                                   "password": "short", "organisation_id": orgs[0]["id"]})
    assert weak.status_code == 422
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer " + reg.json()["access_token"]})
    assert me.json()["email"] == "new@x.com"
    assert client.post("/api/auth/logout", headers={"Authorization": "Bearer " + reg.json()["access_token"]}).status_code == 204


def test_deactivated_user_loses_access(client, auth):
    creator = auth("creator")
    users = client.get("/api/users", headers=auth("admin")).json()
    cid = next(u["id"] for u in users if u["role"] == "creator")
    assert client.patch(f"/api/users/{cid}", headers=auth("admin"), json={"is_active": False}).status_code == 200
    assert client.get("/api/content", headers=creator).status_code == 401
    me = next(u["id"] for u in users if u["role"] == "admin")
    assert client.patch(f"/api/users/{me}", headers=auth("admin"), json={"role": "creator"}).status_code == 400


def test_rule_crud_and_validation(client, auth):
    admin = auth("admin")
    bad = client.post("/api/claims", headers=admin, json={"claim_text": "Best ever", "status": "approved"})
    assert bad.status_code == 422  # approved claim needs evidence
    assert client.post("/api/facts", headers=admin, json={
        "subject": "S", "statement": "s", "correct_value": "1", "match_pattern": "(unclosed"}).status_code == 422
    assert client.post("/api/guidelines", headers=admin, json={
        "category": "required_info", "title": "T", "description": "d"}).status_code == 422
    assert client.post("/api/guidelines", headers=admin, json={
        "category": "nonsense", "title": "T", "description": "d"}).status_code == 422
    g = client.post("/api/guidelines", headers=admin, json={
        "category": "general", "title": "Be kind", "description": "Be kind.", "severity": "Low"}).json()
    upd = client.put(f"/api/guidelines/{g['id']}", headers=admin, json={
        "category": "general", "title": "Be very kind", "description": "Be kind.", "severity": "Low", "is_active": False})
    assert upd.json()["title"] == "Be very kind" and upd.json()["is_active"] is False
    assert client.delete(f"/api/guidelines/{g['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/guidelines/{g['id']}", headers=admin).status_code == 404
    t = client.post("/api/terminology", headers=admin, json={
        "approved_term": "Foo", "incorrect_variants": ["Fo o", " "]}).json()
    assert t["incorrect_variants"] == ["Fo o"]


def test_inactive_rules_are_ignored(client, auth):
    admin, creator = auth("admin"), auth("creator")
    pw = next(p for p in client.get("/api/prohibited-words", headers=admin).json() if p["phrase"] == "never fails")
    client.put(f"/api/prohibited-words/{pw['id']}", headers=admin, json={**pw, "is_active": False})
    sub = create_text(client, creator, "Our platform never fails.")
    res = client.post(f"/api/content/{sub['id']}/analyze", headers=creator).json()
    assert not [i for i in res["issues"] if i["rule_type"] == "prohibited_word"]


def test_clean_content_has_no_issues(client, auth):
    creator = auth("creator")
    sub = create_text(client, creator, "TechNova Cloud helps teams run applications reliably.")
    res = client.post(f"/api/content/{sub['id']}/analyze", headers=creator).json()
    assert res["issues"] == [] and res["status"] == "analyzed"
    assert "AI layer is off" in res["runs"][0]["ai_status"]


def test_uploads_and_validation(client, auth):
    creator = auth("creator")
    # TXT, DOCX, PDF
    for name, kind in (("sample_violations.txt", "txt"), ("sample_violations.docx", "docx"), ("sample_violations.pdf", "pdf")):
        data = (SAMPLES / name).read_bytes()
        r = client.post("/api/content/upload", headers=creator, files={"file": (name, data)}, data={"title": name})
        assert r.status_code == 201, (name, r.text)
        assert r.json()["source_type"] == kind and "Tech Nova Cloud" in r.json()["original_text"]
        a = client.post(f"/api/content/{r.json()['id']}/analyze", headers=creator).json()
        assert any(i["rule_type"] == "terminology" for i in a["issues"])
    # unsupported type
    r = client.post("/api/content/upload", headers=creator, files={"file": ("virus.exe", b"MZ\x00")})
    assert r.status_code == 415
    # fake PDF
    r = client.post("/api/content/upload", headers=creator, files={"file": ("fake.pdf", b"not a pdf at all")})
    assert r.status_code == 422 and "valid" in r.json()["detail"]
    # empty
    assert client.post("/api/content/upload", headers=creator, files={"file": ("e.txt", b"")}).status_code == 422
    # too large
    big = b"a" * (10 * 1024 * 1024 + 10)
    assert client.post("/api/content/upload", headers=creator, files={"file": ("big.txt", big)}).status_code == 413
    # path traversal in the file name is neutralised
    r = client.post("/api/content/upload", headers=creator, files={"file": ("../../evil.txt", b"hello world")})
    assert r.status_code == 201 and r.json()["original_filename"] == "evil.txt"
    # blank text
    assert client.post("/api/content", headers=creator, json={"title": "t", "text": "   "}).status_code == 422


def test_docx_missing_alt_text_is_reported(client, auth, tmp_path):
    import docx
    from PIL import Image
    img = tmp_path / "pic.png"
    Image.new("RGB", (40, 40), "red").save(img)
    d = docx.Document()
    d.add_paragraph("TechNova Cloud brochure.")
    d.add_picture(str(img))
    f = tmp_path / "with_image.docx"
    d.save(f)
    creator = auth("creator")
    r = client.post("/api/content/upload", headers=creator, files={"file": ("with_image.docx", f.read_bytes())})
    assert r.status_code == 201 and r.json()["extraction_meta"]["images_without_alt"] == 1
    a = client.post(f"/api/content/{r.json()['id']}/analyze", headers=creator).json()
    assert any(i["category"] == "Accessibility" for i in a["issues"])


def test_image_ocr_upload(client, auth):
    import shutil
    import pytest
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract OCR is not installed")
    creator = auth("creator")
    data = (SAMPLES / "sample_violations.png").read_bytes()
    r = client.post("/api/content/upload", headers=creator, files={"file": ("sample.png", data)})
    assert r.status_code == 201, r.text
    assert r.json()["source_type"] == "image"
    a = client.post(f"/api/content/{r.json()['id']}/analyze", headers=creator).json()
    assert any(i["rule_type"] == "terminology" for i in a["issues"])   # text in the image was checked


def test_image_without_text_gives_clear_error(client, auth, tmp_path):
    import shutil
    import pytest
    from PIL import Image
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract OCR is not installed")
    p = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), "white").save(p)
    r = client.post("/api/content/upload", headers=auth("creator"), files={"file": ("blank.png", p.read_bytes())})
    assert r.status_code == 422 and "No readable text" in r.json()["detail"]
