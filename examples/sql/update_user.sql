-- User update SQL
UPDATE users
SET
    name = /* name */'default_name',
    email = /* email */'default@example.com',
    department = /* department */'General'
WHERE
    id = /* id */1
