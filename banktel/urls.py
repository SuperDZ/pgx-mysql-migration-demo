from django.urls import path

from .views import (
    demo_customers,
    demo_risk,
    demo_txns,
    txn_ack,
    txn_approve,
    txn_book,
    txn_clear,
    txn_reject,
    txn_submit_review,
)

urlpatterns = [
    path("customers", demo_customers, name="demo_customers"),
    path("txns", demo_txns, name="demo_txns"),
    path("risk", demo_risk, name="demo_risk"),
    path("txns/<int:txn_id>/submit-review", txn_submit_review, name="txn_submit_review"),
    path("txns/<int:txn_id>/approve", txn_approve, name="txn_approve"),
    path("txns/<int:txn_id>/reject", txn_reject, name="txn_reject"),
    path("txns/<int:txn_id>/book", txn_book, name="txn_book"),
    path("txns/<int:txn_id>/clear", txn_clear, name="txn_clear"),
    path("txns/<int:txn_id>/ack", txn_ack, name="txn_ack"),
]
