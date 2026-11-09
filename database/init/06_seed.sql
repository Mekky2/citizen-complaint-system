-- =============================================================================
-- EG Civic Operations — Seed Data
-- =============================================================================
-- Idempotent (ON CONFLICT DO NOTHING on each unique name), so this file is safe
-- to re-run against a database that already has this seed data.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Roles
-- -----------------------------------------------------------------------------

INSERT INTO roles (name) VALUES
    ('citizen'),
    ('supervisor'),
    ('technician'),
    ('admin')
ON CONFLICT (name) DO NOTHING;


-- -----------------------------------------------------------------------------
-- Departments
-- -----------------------------------------------------------------------------

INSERT INTO departments (name, description) VALUES
    ('Roads & Bridges Authority', 'Road surface, potholes, bridges, traffic infrastructure'),
    ('Cleaning & Beautification Authority', 'Waste collection, street cleaning, public spaces'),
    ('Electricity Company', 'Street lighting, electrical infrastructure faults'),
    ('Water & Wastewater Company', 'Water mains, sewage, drainage'),
    ('Local Administration', 'General governorate/local-administration matters not owned by a specialized authority')
ON CONFLICT (name) DO NOTHING;


-- -----------------------------------------------------------------------------
-- Categories (default_department_id resolved by name via subselect, so this
-- file does not depend on knowing the departments' generated UUIDs)
-- -----------------------------------------------------------------------------

INSERT INTO categories (name, default_department_id)
SELECT 'Pothole / road damage', id FROM departments WHERE name = 'Roads & Bridges Authority'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, default_department_id)
SELECT 'Garbage buildup', id FROM departments WHERE name = 'Cleaning & Beautification Authority'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, default_department_id)
SELECT 'Street light outage', id FROM departments WHERE name = 'Electricity Company'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, default_department_id)
SELECT 'Water main break', id FROM departments WHERE name = 'Water & Wastewater Company'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, default_department_id)
SELECT 'Sewage overflow', id FROM departments WHERE name = 'Water & Wastewater Company'
ON CONFLICT (name) DO NOTHING;

INSERT INTO categories (name, default_department_id)
SELECT 'Other', id FROM departments WHERE name = 'Local Administration'
ON CONFLICT (name) DO NOTHING;
