"""Live end-to-end check against a RUNNING server (real HTTP, real database).

    python scripts/live_smoke_test.py [http://localhost:8000]

Walks through the whole demo workflow using the seeded demonstration accounts.
"""
import sys

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/") + "/api"
c = httpx.Client(timeout=30)
ok = True


def step(name, cond, extra=""):
    global ok
    ok &= bool(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")


def login(email, pw):
    r = c.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


admin = login("admin@technova.demo", "Admin@123")
creator = login("creator@technova.demo", "Creator@123")
reviewer = login("reviewer@technova.demo", "Reviewer@123")
step("1. Admin, Creator and Reviewer can log in", True)

rules = {k: len(c.get(f"{BASE}/{k}", headers=admin).json()) for k in ("guidelines", "facts", "terminology", "prohibited-words", "claims")}
step("2. Admin sees the stored brand rules", all(rules.values()), str(rules))

r = c.post(f"{BASE}/prohibited-words", headers=creator, json={"phrase": "x"})
step("3. Creator is blocked from editing rules (403)", r.status_code == 403)

sub = c.get(f"{BASE}/content", headers=creator).json()[0]            # the seeded demo draft
step("4. Creator sees the seeded demo content", "DEMO" in sub["title"], sub["title"])
res = c.post(f"{BASE}/content/{sub['id']}/analyze", headers=creator).json()
issues = res["issues"]
step("5. Analysis ran and found violations", len(issues) >= 6, f"{len(issues)} issues")
for i in issues:
    print(f"        {i['severity']:<8} {i['title'][:58]:<58} <- {i['rule_reference'][:46]}")
refs = " ".join(i["rule_reference"] for i in issues)
step("6. Terminology, price, claim and prohibited-phrase issues cite stored rules",
     all(k in refs for k in ("Terminology", "Approved fact", "Claim", "Prohibited word")))
step("7. Every issue has an explanation, source rule and suggestion",
     all(i["explanation"] and i["rule_snapshot"] and i["suggestion"] for i in issues))
step("8. Unverifiable claim is labelled 'requires human verification'",
     any(i["requires_human_verification"] and i["rule_type"] == "claim" for i in issues))

for i in issues:
    s = i["suggestion"]
    if s["action"] != "manual":
        c.patch(f"{BASE}/suggestions/{s['id']}", headers=creator, json={"status": "accepted"})
prev = c.get(f"{BASE}/content/{sub['id']}/revised-preview", headers=creator).json()
step("9. Accepted suggestions produce a revised preview", "TechNova Cloud" in prev["revised_text"] and "₹999 per month" in prev["revised_text"])
d = c.post(f"{BASE}/content/{sub['id']}/apply-suggestions", headers=creator).json()
step("10. Original text is preserved; status returns to draft", d["original_text"] != d["revised_text"] and d["status"] == "draft")
d = c.post(f"{BASE}/content/{sub['id']}/analyze", headers=creator).json()
step("11. Re-analysis shows fewer issues", len(d["issues"]) < len(issues), f"{len(issues)} -> {len(d['issues'])}")

r = c.post(f"{BASE}/content/{sub['id']}/submit", headers=creator)
step("12. Creator submits for review", r.status_code == 200 and r.json()["status"] == "submitted")
r = c.post(f"{BASE}/content/{sub['id']}/review", headers=admin, json={"decision": "approved"})
step("13. Admin cannot approve (403)", r.status_code == 403)
q = c.get(f"{BASE}/reviews/queue", headers=reviewer).json()
step("14. Reviewer sees it in the queue", any(x["id"] == sub["id"] for x in q))
r = c.post(f"{BASE}/content/{sub['id']}/review", headers=reviewer, json={"decision": "rejected"})
step("15. Rejecting without a reason is refused (422)", r.status_code == 422)
r = c.post(f"{BASE}/content/{sub['id']}/review", headers=reviewer, json={"decision": "approved", "comment": "Verified by reviewer."})
step("16. Human reviewer approves", r.status_code == 200 and r.json()["status"] == "approved")
dash = c.get(f"{BASE}/dashboard", headers=creator).json()
step("17. Dashboard shows the approved item", dash["approved"] >= 1, f"approved={dash['approved']}")
hist = c.get(f"{BASE}/content/{sub['id']}/history", headers=admin).json()
step("18. Audit history recorded the steps", {"content.analyzed", "content.submitted", "review.approved"} <= {h["action"] for h in hist})
print("\nRESULT:", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)
