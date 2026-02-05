-- User search SQL (with dynamic conditions)
-- 2way SQL: When a parameter is None, that condition line is automatically removed
SELECT
    id,
    name,
    email,
    department,
    created_at
FROM users
WHERE
    id = /* $id */1
    AND name LIKE /* $name_pattern */'%test%' ESCAPE '#'
    AND department = /* $department */'Sales'
    AND id IN /* $ids */(1, 2, 3)
ORDER BY id
