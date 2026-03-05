from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import RiskCase, Txn, TxnCorePhase
from .services.txn_flow import apply_txn_action, available_actions_for_txn, user_role_flags
from .sql_runner import load_named_queries, run_named_query

LOGGER = logging.getLogger("banktel")


def _none_if_blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _to_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _to_decimal(value: str | None, default: Decimal) -> Decimal:
    try:
        return Decimal(value) if value not in (None, "") else default
    except Exception:
        return default


def _render_secondary_demo(
    request,
    *,
    template_name: str,
    page_title: str,
    sql_filename: str,
    default_query_id: str,
    params: dict[str, Any],
    form_fields: list[str],
    field_labels: dict[str, str],
):
    available_queries = list(load_named_queries(sql_filename).keys())
    query_id = request.GET.get("query", default_query_id)
    if query_id not in available_queries:
        query_id = default_query_id

    result = run_named_query(sql_filename=sql_filename, query_id=query_id, params=params)

    return render(
        request,
        template_name,
        {
            "page_title": page_title,
            "sql_filename": sql_filename,
            "db_target": settings.DB_TARGET,
            "available_queries": available_queries,
            "selected_query": query_id,
            "form_items": [
                {"name": f, "label": field_labels.get(f, f), "value": params.get(f)}
                for f in form_fields
            ],
            "rows_count": len(result["rows"]),
            "raw_sql": result["raw_sql"],
            "pre_sql": result["pre_sql"] or "",
            "final_sql": result["final_sql"],
            "columns": result["columns"],
            "rows": result["rows"],
            "error": result["error"],
        },
    )


def _build_txn_timeline(phase: str) -> list[dict[str, Any]]:
    base_chain = [
        (TxnCorePhase.RECEIVED, "受理"),
        (TxnCorePhase.REVIEW_PENDING, "待复核"),
        (TxnCorePhase.APPROVED, "复核通过"),
        (TxnCorePhase.BOOKED, "记账完成"),
        (TxnCorePhase.CLEARED, "清算完成"),
        (TxnCorePhase.ACKED, "回执完成"),
    ]
    order = {item[0]: idx for idx, item in enumerate(base_chain)}
    active_idx = order.get(phase, 0)

    timeline = []
    for idx, (phase_code, phase_label) in enumerate(base_chain):
        timeline.append(
            {
                "phase": phase_code,
                "label": phase_label,
                "done": idx < active_idx,
                "current": idx == active_idx and phase_code == phase,
            }
        )

    if phase == TxnCorePhase.REJECTED:
        timeline.append(
            {
                "phase": TxnCorePhase.REJECTED,
                "label": "复核拒绝",
                "done": False,
                "current": True,
                "is_rejected": True,
            }
        )
    return timeline


def demo_customers(request):
    params = {
        "status": _none_if_blank(request.GET.get("status")),
        "mobile": _none_if_blank(request.GET.get("mobile")),
        "account_status": _none_if_blank(request.GET.get("account_status")),
        "offset": _to_int(request.GET.get("offset"), 0),
        "count": _to_int(request.GET.get("count"), 20),
    }
    return _render_secondary_demo(
        request,
        template_name="banktel/demo_customers.html",
        page_title="客户主数据中心",
        sql_filename="customers.sql",
        default_query_id="customers_null_eq_list",
        params=params,
        form_fields=["status", "mobile", "account_status", "offset", "count"],
        field_labels={
            "status": "客户状态",
            "mobile": "手机号",
            "account_status": "账户状态",
            "offset": "起始偏移",
            "count": "返回条数",
        },
    )


def demo_txns(request):
    params = {
        "customer_no": _none_if_blank(request.GET.get("customer_no")),
        "status": _none_if_blank(request.GET.get("status")),
        "start_at": _none_if_blank(request.GET.get("start_at")),
        "end_at": _none_if_blank(request.GET.get("end_at")),
        "offset": _to_int(request.GET.get("offset"), 0),
        "count": _to_int(request.GET.get("count"), 20),
    }

    available_queries = list(load_named_queries("txns.sql").keys())
    query_id = request.GET.get("query", "txns_list")
    if query_id not in available_queries:
        query_id = "txns_list"
    sql_result = run_named_query(sql_filename="txns.sql", query_id=query_id, params=params)
    base_query_params = request.GET.copy()
    if "txn_id" in base_query_params:
        del base_query_params["txn_id"]
    base_query = base_query_params.urlencode()

    worklist = list(
        Txn.objects.select_related("customer", "account", "maker_user", "checker_user")
        .order_by("-txn_at", "-id")[:60]
    )
    selected_txn_id = _to_int(request.GET.get("txn_id"), 0)
    selected_txn = next((item for item in worklist if item.id == selected_txn_id), None)
    if selected_txn is None and worklist:
        selected_txn = worklist[0]

    role_flags = user_role_flags(request.user)
    actions = []
    timeline = []
    risk_cases = []
    if selected_txn is not None:
        actions = available_actions_for_txn(selected_txn, request.user)
        timeline = _build_txn_timeline(selected_txn.core_phase)
        risk_cases = list(
            RiskCase.objects.filter(
                customer=selected_txn.customer, account=selected_txn.account
            ).order_by("-detected_at")[:10]
        )

    return render(
        request,
        "banktel/demo_txn_console.html",
        {
            "page_title": "对公转账作战台",
            "sql_filename": "txns.sql",
            "db_target": settings.DB_TARGET,
            "available_queries": available_queries,
            "selected_query": query_id,
            "form_items": [
                {"name": "customer_no", "label": "客户编号", "value": params.get("customer_no")},
                {"name": "status", "label": "交易状态", "value": params.get("status")},
                {"name": "start_at", "label": "开始时间", "value": params.get("start_at")},
                {"name": "end_at", "label": "结束时间", "value": params.get("end_at")},
                {"name": "offset", "label": "起始偏移", "value": params.get("offset")},
                {"name": "count", "label": "返回条数", "value": params.get("count")},
            ],
            "worklist": worklist,
            "selected_txn": selected_txn,
            "txn_timeline": timeline,
            "risk_cases": risk_cases,
            "action_buttons": actions,
            "role_flags": role_flags,
            "rows_count": len(sql_result["rows"]),
            "raw_sql": sql_result["raw_sql"],
            "pre_sql": sql_result["pre_sql"] or "",
            "final_sql": sql_result["final_sql"],
            "columns": sql_result["columns"],
            "rows": sql_result["rows"],
            "error": sql_result["error"],
            "base_query": base_query,
        },
    )


def demo_risk(request):
    params = {
        "status": _none_if_blank(request.GET.get("status")),
        "min_amount": _to_decimal(request.GET.get("min_amount"), Decimal("0")),
        "offset": _to_int(request.GET.get("offset"), 0),
        "count": _to_int(request.GET.get("count"), 20),
    }
    return _render_secondary_demo(
        request,
        template_name="banktel/demo_risk.html",
        page_title="风险案件中心",
        sql_filename="risk.sql",
        default_query_id="risk_active_cases",
        params=params,
        form_fields=["status", "min_amount", "offset", "count"],
        field_labels={
            "status": "案件状态",
            "min_amount": "最低风险金额",
            "offset": "起始偏移",
            "count": "返回条数",
        },
    )


def _handle_txn_action(request, txn_id: int, action: str):
    txn = get_object_or_404(Txn, id=txn_id)
    try:
        result = apply_txn_action(txn=txn, action=action, user=request.user)
        return JsonResponse(
            {
                "ok": True,
                "txn_phase": result["txn_phase"],
                "risk_phase": result["risk_phase"],
                "message": result["message"],
            }
        )
    except PermissionDenied as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=403)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception as exc:
        LOGGER.exception(
            "txn_action_failed action=%s txn_id=%s operator=%s",
            action,
            txn_id,
            request.user.username if request.user.is_authenticated else "anonymous",
        )
        return JsonResponse({"ok": False, "error": f"系统异常: {exc}"}, status=500)


@login_required
@require_POST
def txn_submit_review(request, txn_id: int):
    return _handle_txn_action(request, txn_id, "submit-review")


@login_required
@require_POST
def txn_approve(request, txn_id: int):
    return _handle_txn_action(request, txn_id, "approve")


@login_required
@require_POST
def txn_reject(request, txn_id: int):
    return _handle_txn_action(request, txn_id, "reject")


@login_required
@require_POST
def txn_book(request, txn_id: int):
    return _handle_txn_action(request, txn_id, "book")


@login_required
@require_POST
def txn_clear(request, txn_id: int):
    return _handle_txn_action(request, txn_id, "clear")


@login_required
@require_POST
def txn_ack(request, txn_id: int):
    return _handle_txn_action(request, txn_id, "ack")
