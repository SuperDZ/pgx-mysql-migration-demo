from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from banktel.models import RiskCase, RiskPhase, Txn, TxnCorePhase

APP_LOGGER = logging.getLogger("banktel")
SQL_LOGGER = logging.getLogger("sql")

MAKER_GROUP = "txn_maker"
CHECKER_GROUP = "txn_checker"

MAKER_ACTIONS = {"submit-review", "book", "clear", "ack"}
CHECKER_ACTIONS = {"approve", "reject"}

ACTION_TRANSITIONS = {
    "submit-review": (TxnCorePhase.RECEIVED, TxnCorePhase.REVIEW_PENDING),
    "approve": (TxnCorePhase.REVIEW_PENDING, TxnCorePhase.APPROVED),
    "reject": (TxnCorePhase.REVIEW_PENDING, TxnCorePhase.REJECTED),
    "book": (TxnCorePhase.APPROVED, TxnCorePhase.BOOKED),
    "clear": (TxnCorePhase.BOOKED, TxnCorePhase.CLEARED),
    "ack": (TxnCorePhase.CLEARED, TxnCorePhase.ACKED),
}

ACTION_LABELS = {
    "submit-review": "提交复核",
    "approve": "复核通过",
    "reject": "复核拒绝",
    "book": "记账",
    "clear": "清算",
    "ack": "回执",
}


def user_role_flags(user) -> dict[str, bool]:
    if not user.is_authenticated:
        return {"is_maker": False, "is_checker": False}
    groups = set(user.groups.values_list("name", flat=True))
    return {
        "is_maker": MAKER_GROUP in groups,
        "is_checker": CHECKER_GROUP in groups,
    }


def available_actions_for_txn(txn: Txn, user) -> list[dict[str, str]]:
    role_flags = user_role_flags(user)
    available: list[dict[str, str]] = []
    for action, (source_phase, _target_phase) in ACTION_TRANSITIONS.items():
        if txn.core_phase != source_phase:
            continue
        if action in MAKER_ACTIONS and not role_flags["is_maker"]:
            continue
        if action in CHECKER_ACTIONS and not role_flags["is_checker"]:
            continue
        available.append({"action": action, "label": ACTION_LABELS[action]})
    return available


def _assert_action_permission(action: str, user) -> None:
    if not user.is_authenticated:
        raise PermissionDenied("请先登录后再执行操作。")

    role_flags = user_role_flags(user)
    if action in MAKER_ACTIONS and not role_flags["is_maker"]:
        raise PermissionDenied("当前用户无经办权限。")
    if action in CHECKER_ACTIONS and not role_flags["is_checker"]:
        raise PermissionDenied("当前用户无复核权限。")


def _next_risk_phase(action: str, current_phase: str) -> str | None:
    if action == "submit-review" and current_phase == RiskPhase.OPEN:
        return RiskPhase.REVIEWING
    if action == "reject" and current_phase in {RiskPhase.OPEN, RiskPhase.REVIEWING}:
        return RiskPhase.BLOCKED
    if action == "clear" and current_phase == RiskPhase.REVIEWING:
        return RiskPhase.RELEASED
    if action == "ack" and current_phase == RiskPhase.RELEASED:
        return RiskPhase.CLOSED
    return None


@transaction.atomic
def apply_txn_action(*, txn: Txn, action: str, user) -> dict[str, Any]:
    if action not in ACTION_TRANSITIONS:
        raise ValueError(f"不支持的操作动作: {action}")

    _assert_action_permission(action, user)

    expected_from, to_phase = ACTION_TRANSITIONS[action]
    if txn.core_phase != expected_from:
        raise ValueError(
            f"当前状态 {txn.core_phase} 不能执行动作 {action}，期望状态为 {expected_from}。"
        )

    now = timezone.now()
    prev_phase = txn.core_phase

    txn.core_phase = to_phase
    txn.phase_updated_at = now
    update_fields = ["core_phase", "phase_updated_at"]

    if action in MAKER_ACTIONS:
        txn.maker_user = user
        update_fields.append("maker_user")
    if action in CHECKER_ACTIONS:
        txn.checker_user = user
        update_fields.append("checker_user")

    txn.save(update_fields=update_fields)

    risk_case_ids: list[int] = []
    risk_phase_summary = "N/A"
    risk_queryset = (
        RiskCase.objects.select_for_update()
        .filter(customer=txn.customer, account=txn.account)
        .exclude(risk_phase=RiskPhase.CLOSED)
        .order_by("-id")
    )

    for risk_case in risk_queryset:
        next_phase = _next_risk_phase(action, risk_case.risk_phase)
        if not next_phase:
            continue
        prev_risk_phase = risk_case.risk_phase
        risk_case.risk_phase = next_phase
        risk_case.linked_txn_no = txn.txn_no
        risk_case.reviewed_by = user
        risk_case.reviewed_at = now
        risk_case.save(
            update_fields=["risk_phase", "linked_txn_no", "reviewed_by", "reviewed_at"]
        )
        risk_case_ids.append(risk_case.id)
        risk_phase_summary = next_phase
        APP_LOGGER.info(
            "risk_flow action=%s risk_case_id=%s txn_id=%s before=%s after=%s operator=%s",
            action,
            risk_case.id,
            txn.id,
            prev_risk_phase,
            next_phase,
            user.username,
        )
        SQL_LOGGER.info(
            "risk_flow action=%s risk_case_id=%s txn_id=%s before=%s after=%s operator=%s",
            action,
            risk_case.id,
            txn.id,
            prev_risk_phase,
            next_phase,
            user.username,
        )

    APP_LOGGER.info(
        "txn_flow action=%s txn_id=%s txn_no=%s before=%s after=%s operator=%s risk_case_ids=%s",
        action,
        txn.id,
        txn.txn_no,
        prev_phase,
        to_phase,
        user.username,
        risk_case_ids,
    )
    SQL_LOGGER.info(
        "txn_flow action=%s txn_id=%s txn_no=%s before=%s after=%s operator=%s risk_case_ids=%s",
        action,
        txn.id,
        txn.txn_no,
        prev_phase,
        to_phase,
        user.username,
        risk_case_ids,
    )

    return {
        "txn_phase": to_phase,
        "risk_phase": risk_phase_summary,
        "message": f"动作[{ACTION_LABELS[action]}]执行成功",
    }
