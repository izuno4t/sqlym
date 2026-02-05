SELECT id, user_id, product_name, quantity, total_price, ordered_at
FROM orders
WHERE user_id = /* user_id */1
ORDER BY ordered_at DESC
