-- name: txns_list
SELECT
  t.id,
  t.txn_no,
  c.customer_no,
  a.account_no,
  t.status,
  t.amount,
  t.txn_at
FROM banktel_txn t
JOIN banktel_customer c ON c.id = t.customer_id
JOIN banktel_account a ON a.id = t.account_id
WHERE ({status} IS NULL OR t.status = {status})
  AND ({start_at} IS NULL OR t.txn_at >= {start_at})
  AND ({end_at} IS NULL OR t.txn_at <= {end_at})
ORDER BY t.txn_at DESC, t.id DESC
LIMIT {offset},{count};

-- name: txns_by_customer
SELECT
  t.id,
  t.txn_no,
  c.customer_no,
  a.account_no,
  t.status,
  t.amount,
  t.txn_at
FROM banktel_txn t
JOIN banktel_customer c ON c.id = t.customer_id
JOIN banktel_account a ON a.id = t.account_id
WHERE ({customer_no} IS NULL OR c.customer_no = {customer_no})
  AND ({status} IS NULL OR t.status = {status})
ORDER BY t.customer_id ASC, t.txn_at DESC, t.id DESC
LIMIT {offset},{count};
