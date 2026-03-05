-- name: risk_active_cases
SELECT
  r.id,
  r.case_no,
  c.customer_no,
  r.status,
  r.risk_phase,
  r.linked_txn_no,
  r.risk_amount,
  r.detected_at
FROM banktel_riskcase r
JOIN banktel_customer c ON c.id = r.customer_id
WHERE (r.status = {status} OR {status} IS NULL)
  && !(r.risk_amount < {min_amount})
ORDER BY r.detected_at DESC, r.id DESC
LIMIT {count} OFFSET {offset};

-- name: risk_unclosed_manual
SELECT
  r.id,
  r.case_no,
  c.customer_no,
  r.status,
  r.risk_phase,
  r.linked_txn_no,
  r.risk_amount,
  r.detected_at
FROM banktel_riskcase r
JOIN banktel_customer c ON c.id = r.customer_id
WHERE (r.status = {status} OR {status} IS NULL)
  && !(JSON_EXTRACT(r.rules_json, '$.manual_close') = true)
ORDER BY r.detected_at DESC, r.id DESC
LIMIT {count} OFFSET {offset};
