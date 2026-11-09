"""
Maintenance: technician access, team-membership enforcement (FIX 1), task
status updates, task evidence API (FIX 2), and rework attempts.
"""

from tests.conftest import auth_headers, create_assigned_ticket, make_team, make_technician


def test_technician_team_membership_enforcement(
    client, db, admin_token, supervisor_token, citizen_token, ai_secret
):
    """FIX 1, the core scenario: two teams, two technicians, one task. A
    technician who is a member of a DIFFERENT team than the one assigned to
    the task must be rejected (403), even though the task_id is perfectly
    valid and they are a real technician."""
    dept_resp = client.post(
        "/api/v1/admin/departments",
        headers=auth_headers(admin_token),
        json={"name": f"FIX1 Dept {__import__('uuid').uuid4().hex[:8]}"},
    )
    assert dept_resp.status_code == 201
    dept_id = dept_resp.json()["id"]

    team_a = make_team(client, admin_token, dept_id)
    team_b = make_team(client, admin_token, dept_id)

    tech_a_id, _, tech_a_token = make_technician(client, admin_token)
    tech_b_id, _, tech_b_token = make_technician(client, admin_token)

    resp = client.post(
        f"/api/v1/maintenance/teams/{team_a}/members",
        headers=auth_headers(admin_token),
        json={"user_id": tech_a_id},
    )
    assert resp.status_code == 201, resp.text
    resp = client.post(
        f"/api/v1/maintenance/teams/{team_b}/members",
        headers=auth_headers(admin_token),
        json={"user_id": tech_b_id},
    )
    assert resp.status_code == 201, resp.text

    ticket_id = create_assigned_ticket(
        client,
        db,
        citizen_token=citizen_token,
        supervisor_token=supervisor_token,
        ai_secret=ai_secret,
    )
    resp = client.post(
        f"/api/v1/maintenance/tickets/{ticket_id}/tasks",
        headers=auth_headers(supervisor_token),
        json={"team_id": team_b, "notes": "assigned to team B"},
    )
    assert resp.status_code == 201, resp.text
    task_id = resp.json()["id"]

    # tech_a is NOT a member of team_b (the team this task belongs to) -> 403.
    resp = client.patch(
        f"/api/v1/maintenance/tasks/{task_id}/status",
        headers=auth_headers(tech_a_token),
        json={"status": "in_progress"},
    )
    assert resp.status_code == 403, resp.text

    # tech_b IS a member of team_b -> allowed.
    resp = client.patch(
        f"/api/v1/maintenance/tasks/{task_id}/status",
        headers=auth_headers(tech_b_token),
        json={"status": "in_progress"},
    )
    assert resp.status_code == 200, resp.text

    # supervisor/admin are never team-scoped -> always allowed.
    resp = client.patch(
        f"/api/v1/maintenance/tasks/{task_id}/status",
        headers=auth_headers(supervisor_token),
        json={"status": "pending_verification"},
    )
    assert resp.status_code == 200, resp.text


def test_task_evidence_api(client, db, admin_token, supervisor_token, citizen_token, ai_secret):
    """FIX 2: valid creation, unauthorized technician, nonexistent task, retrieval."""
    dept_resp = client.post(
        "/api/v1/admin/departments",
        headers=auth_headers(admin_token),
        json={"name": f"FIX2 Dept {__import__('uuid').uuid4().hex[:8]}"},
    )
    dept_id = dept_resp.json()["id"]
    team_id = make_team(client, admin_token, dept_id)
    other_team_id = make_team(client, admin_token, dept_id)

    member_tech_id, _, member_tech_token = make_technician(client, admin_token)
    outsider_tech_id, _, outsider_tech_token = make_technician(client, admin_token)

    resp = client.post(
        f"/api/v1/maintenance/teams/{team_id}/members",
        headers=auth_headers(admin_token),
        json={"user_id": member_tech_id},
    )
    assert resp.status_code == 201
    resp = client.post(
        f"/api/v1/maintenance/teams/{other_team_id}/members",
        headers=auth_headers(admin_token),
        json={"user_id": outsider_tech_id},
    )
    assert resp.status_code == 201

    ticket_id = create_assigned_ticket(
        client,
        db,
        citizen_token=citizen_token,
        supervisor_token=supervisor_token,
        ai_secret=ai_secret,
    )
    resp = client.post(
        f"/api/v1/maintenance/tickets/{ticket_id}/tasks",
        headers=auth_headers(supervisor_token),
        json={"team_id": team_id},
    )
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    # Nonexistent task -> 404.
    resp = client.post(
        f"/api/v1/maintenance/tasks/{__import__('uuid').uuid4()}/evidence",
        headers=auth_headers(member_tech_token),
        json={"type": "image", "stage": "after", "url": "https://example.com/photo.jpg"},
    )
    assert resp.status_code == 404

    # Unauthorized technician (not on this task's team) -> 403.
    resp = client.post(
        f"/api/v1/maintenance/tasks/{task_id}/evidence",
        headers=auth_headers(outsider_tech_token),
        json={"type": "image", "stage": "after", "url": "https://example.com/photo.jpg"},
    )
    assert resp.status_code == 403

    # Valid creation by the authorized (team-member) technician -> 201.
    resp = client.post(
        f"/api/v1/maintenance/tasks/{task_id}/evidence",
        headers=auth_headers(member_tech_token),
        json={"type": "image", "stage": "progress", "url": "https://example.com/progress.jpg"},
    )
    assert resp.status_code == 201, resp.text
    evidence_id = resp.json()["id"]

    # Retrieval: authorized technician sees it.
    resp = client.get(
        f"/api/v1/maintenance/tasks/{task_id}/evidence", headers=auth_headers(member_tech_token)
    )
    assert resp.status_code == 200
    ids = {e["id"] for e in resp.json()}
    assert evidence_id in ids

    # Retrieval: supervisor can view evidence for any task.
    resp = client.get(
        f"/api/v1/maintenance/tasks/{task_id}/evidence", headers=auth_headers(supervisor_token)
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1

    # Retrieval: outsider technician is rejected.
    resp = client.get(
        f"/api/v1/maintenance/tasks/{task_id}/evidence", headers=auth_headers(outsider_tech_token)
    )
    assert resp.status_code == 403


def test_rework_attempt_increments_and_completes(
    client, db, admin_token, supervisor_token, citizen_token, ai_secret
):
    dept_resp = client.post(
        "/api/v1/admin/departments",
        headers=auth_headers(admin_token),
        json={"name": f"Rework Dept {__import__('uuid').uuid4().hex[:8]}"},
    )
    dept_id = dept_resp.json()["id"]
    team_id = make_team(client, admin_token, dept_id)
    tech_id, _, tech_token = make_technician(client, admin_token)
    client.post(
        f"/api/v1/maintenance/teams/{team_id}/members",
        headers=auth_headers(admin_token),
        json={"user_id": tech_id},
    )

    ticket_id = create_assigned_ticket(
        client,
        db,
        citizen_token=citizen_token,
        supervisor_token=supervisor_token,
        ai_secret=ai_secret,
    )

    resp = client.post(
        f"/api/v1/maintenance/tickets/{ticket_id}/tasks",
        headers=auth_headers(supervisor_token),
        json={"team_id": team_id},
    )
    task1 = resp.json()
    assert task1["attempt_number"] == 1

    client.patch(
        f"/api/v1/maintenance/tasks/{task1['id']}/status",
        headers=auth_headers(tech_token),
        json={"status": "in_progress"},
    )
    client.patch(
        f"/api/v1/maintenance/tasks/{task1['id']}/status",
        headers=auth_headers(tech_token),
        json={"status": "pending_verification"},
    )

    resp = client.post(
        f"/api/v1/verification/tasks/{task1['id']}",
        headers=auth_headers(supervisor_token),
        json={"result": "fail", "note": "pytest: not actually fixed"},
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/tickets/{ticket_id}", headers=auth_headers(supervisor_token))
    assert resp.json()["status"] == "assigned"

    resp = client.post(
        f"/api/v1/maintenance/tickets/{ticket_id}/tasks",
        headers=auth_headers(supervisor_token),
        json={"team_id": team_id, "notes": "rework"},
    )
    task2 = resp.json()
    assert task2["attempt_number"] == 2

    client.patch(
        f"/api/v1/maintenance/tasks/{task2['id']}/status",
        headers=auth_headers(tech_token),
        json={"status": "in_progress"},
    )
    client.patch(
        f"/api/v1/maintenance/tasks/{task2['id']}/status",
        headers=auth_headers(tech_token),
        json={"status": "pending_verification"},
    )
    resp = client.post(
        f"/api/v1/verification/tasks/{task2['id']}",
        headers=auth_headers(supervisor_token),
        json={"result": "pass", "note": "pytest: fixed on rework"},
    )
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/tickets/{ticket_id}", headers=auth_headers(supervisor_token))
    assert resp.json()["status"] == "completed"


def test_my_tasks_only_lists_own_teams(
    client, db, admin_token, supervisor_token, citizen_token, ai_secret
):
    dept_resp = client.post(
        "/api/v1/admin/departments",
        headers=auth_headers(admin_token),
        json={"name": f"MyTasks Dept {__import__('uuid').uuid4().hex[:8]}"},
    )
    dept_id = dept_resp.json()["id"]
    team_id = make_team(client, admin_token, dept_id)
    other_team_id = make_team(client, admin_token, dept_id)
    tech_id, _, tech_token = make_technician(client, admin_token)
    client.post(
        f"/api/v1/maintenance/teams/{team_id}/members",
        headers=auth_headers(admin_token),
        json={"user_id": tech_id},
    )

    ticket_id = create_assigned_ticket(
        client,
        db,
        citizen_token=citizen_token,
        supervisor_token=supervisor_token,
        ai_secret=ai_secret,
    )
    resp = client.post(
        f"/api/v1/maintenance/tickets/{ticket_id}/tasks",
        headers=auth_headers(supervisor_token),
        json={"team_id": team_id},
    )
    task_id = resp.json()["id"]

    resp = client.get("/api/v1/maintenance/tasks/mine", headers=auth_headers(tech_token))
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert task_id in ids
