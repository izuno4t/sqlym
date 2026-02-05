SELECT id, name, email, department, created_at
FROM users
WHERE
    1 = 1
    AND department = /* $department */'Sales'
ORDER BY id
