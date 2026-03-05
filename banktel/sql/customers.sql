-- name: customers_null_eq_list
SELECT
  c.id,
  c.customer_no,
  c.name,
  c.mobile,
  c.status,
  c.amount_total,
  c.created_at
FROM banktel_customer c
WHERE c.status <=> {status}
  AND c.mobile <=> {mobile}
ORDER BY c.id DESC
LIMIT {count} OFFSET {offset};

-- name: customers_account_null_eq
SELECT
  c.id,
  c.customer_no,
  c.name,
  a.account_no,
  a.status AS account_status,
  a.balance_amount
FROM banktel_customer c
LEFT JOIN banktel_account a ON a.customer_id = c.id
WHERE c.mobile <=> {mobile}
  AND a.status <=> {account_status}
ORDER BY c.id DESC, a.id DESC
LIMIT {count} OFFSET {offset};
