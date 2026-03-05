from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase
from django.utils import timezone

from banktel.models import Account, Customer, RiskCase, RiskPhase, Txn, TxnCorePhase
from banktel.services.txn_flow import apply_txn_action


class TxnFlowServiceTests(TestCase):
    def setUp(self):
        self.maker_group, _ = Group.objects.get_or_create(name="txn_maker")
        self.checker_group, _ = Group.objects.get_or_create(name="txn_checker")

        self.maker = User.objects.create_user("maker", password="pass123456")
        self.maker.groups.add(self.maker_group)

        self.checker = User.objects.create_user("checker", password="pass123456")
        self.checker.groups.add(self.checker_group)

        self.customer = Customer.objects.create(
            customer_no="C1001",
            name="张三",
            mobile="13800000001",
            amount_total="10000.00",
            status="ACTIVE",
            profile_json={"level": "A"},
            tags_json=["corp"],
        )
        self.account = Account.objects.create(
            customer=self.customer,
            account_no="A1001",
            balance_amount="5000.00",
            opened_at=timezone.now(),
            status="NORMAL",
            ledger_json={"book": "001"},
            ext_json={"channel": "柜面"},
        )
        self.txn = Txn.objects.create(
            txn_no="T202603050001",
            customer=self.customer,
            account=self.account,
            amount="888.88",
            txn_at=timezone.now(),
            status="RECEIVED",
            payload_json={"scene": "transfer"},
            tags_json=["priority"],
        )
        self.risk = RiskCase.objects.create(
            case_no="R202603050001",
            customer=self.customer,
            account=self.account,
            risk_amount="888.88",
            detected_at=timezone.now(),
            status="OPEN",
            rules_json={"manual_close": False},
            evidence_json={"score": 82},
        )

    def test_full_happy_path_updates_txn_and_risk(self):
        apply_txn_action(txn=self.txn, action="submit-review", user=self.maker)
        self.txn.refresh_from_db()
        self.risk.refresh_from_db()
        self.assertEqual(self.txn.core_phase, TxnCorePhase.REVIEW_PENDING)
        self.assertEqual(self.risk.risk_phase, RiskPhase.REVIEWING)

        apply_txn_action(txn=self.txn, action="approve", user=self.checker)
        self.txn.refresh_from_db()
        self.assertEqual(self.txn.core_phase, TxnCorePhase.APPROVED)

        apply_txn_action(txn=self.txn, action="book", user=self.maker)
        apply_txn_action(txn=self.txn, action="clear", user=self.maker)
        self.txn.refresh_from_db()
        self.risk.refresh_from_db()
        self.assertEqual(self.txn.core_phase, TxnCorePhase.CLEARED)
        self.assertEqual(self.risk.risk_phase, RiskPhase.RELEASED)

        apply_txn_action(txn=self.txn, action="ack", user=self.maker)
        self.txn.refresh_from_db()
        self.risk.refresh_from_db()
        self.assertEqual(self.txn.core_phase, TxnCorePhase.ACKED)
        self.assertEqual(self.risk.risk_phase, RiskPhase.CLOSED)
        self.assertEqual(self.risk.linked_txn_no, self.txn.txn_no)

    def test_invalid_transition_raises_value_error(self):
        with self.assertRaises(ValueError):
            apply_txn_action(txn=self.txn, action="approve", user=self.checker)

    def test_permission_guard_works(self):
        with self.assertRaises(PermissionDenied):
            apply_txn_action(txn=self.txn, action="approve", user=self.maker)

    def test_reject_sets_risk_blocked(self):
        apply_txn_action(txn=self.txn, action="submit-review", user=self.maker)
        apply_txn_action(txn=self.txn, action="reject", user=self.checker)

        self.txn.refresh_from_db()
        self.risk.refresh_from_db()

        self.assertEqual(self.txn.core_phase, TxnCorePhase.REJECTED)
        self.assertEqual(self.risk.risk_phase, RiskPhase.BLOCKED)
        self.assertEqual(self.risk.reviewed_by, self.checker)


class TxnFlowViewTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.maker_group, _ = Group.objects.get_or_create(name="txn_maker")
        self.checker_group, _ = Group.objects.get_or_create(name="txn_checker")

        self.maker = User.objects.create_user("maker2", password="pass123456")
        self.maker.groups.add(self.maker_group)

        self.checker = User.objects.create_user("checker2", password="pass123456")
        self.checker.groups.add(self.checker_group)

        self.customer = Customer.objects.create(
            customer_no="C2001",
            name="李四",
            mobile="13900000001",
            amount_total="20000.00",
            status="ACTIVE",
            profile_json={"level": "B"},
            tags_json=["vip"],
        )
        self.account = Account.objects.create(
            customer=self.customer,
            account_no="A2001",
            balance_amount="12000.00",
            opened_at=timezone.now(),
            status="NORMAL",
            ledger_json={"book": "002"},
            ext_json={"channel": "网银"},
        )
        self.txn = Txn.objects.create(
            txn_no="T202603050101",
            customer=self.customer,
            account=self.account,
            amount="1200.00",
            txn_at=timezone.now(),
            status="RECEIVED",
            payload_json={"scene": "transfer"},
            tags_json=["normal"],
        )
        self.risk = RiskCase.objects.create(
            case_no="R202603050101",
            customer=self.customer,
            account=self.account,
            risk_amount="1200.00",
            detected_at=timezone.now(),
            status="OPEN",
            rules_json={"manual_close": False},
            evidence_json={"score": 75},
        )

    def test_demo_pages_render(self):
        resp_txns = self.client.get("/demo/txns")
        resp_customers = self.client.get("/demo/customers")
        resp_risk = self.client.get("/demo/risk")

        self.assertEqual(resp_txns.status_code, 200)
        self.assertEqual(resp_customers.status_code, 200)
        self.assertEqual(resp_risk.status_code, 200)
        self.assertContains(resp_txns, "核心交易操作区")

    def test_unauthenticated_post_redirects_to_login(self):
        resp = self.client.post(f"/demo/txns/{self.txn.id}/submit-review")
        self.assertEqual(resp.status_code, 302)

    def test_wrong_role_returns_403(self):
        self.client.login(username="maker2", password="pass123456")
        resp = self.client.post(f"/demo/txns/{self.txn.id}/approve")
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json()["ok"])

    def test_invalid_transition_returns_400(self):
        self.client.login(username="checker2", password="pass123456")
        resp = self.client.post(f"/demo/txns/{self.txn.id}/approve")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()["ok"])

    def test_flow_endpoints_update_txn_and_risk(self):
        self.client.login(username="maker2", password="pass123456")
        resp = self.client.post(f"/demo/txns/{self.txn.id}/submit-review")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["txn_phase"], TxnCorePhase.REVIEW_PENDING)

        self.client.logout()
        self.client.login(username="checker2", password="pass123456")
        resp = self.client.post(f"/demo/txns/{self.txn.id}/approve")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["txn_phase"], TxnCorePhase.APPROVED)

        self.client.logout()
        self.client.login(username="maker2", password="pass123456")
        resp = self.client.post(f"/demo/txns/{self.txn.id}/book")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(f"/demo/txns/{self.txn.id}/clear")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["risk_phase"], RiskPhase.RELEASED)
        resp = self.client.post(f"/demo/txns/{self.txn.id}/ack")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["txn_phase"], TxnCorePhase.ACKED)
        self.assertEqual(resp.json()["risk_phase"], RiskPhase.CLOSED)

        self.txn.refresh_from_db()
        self.risk.refresh_from_db()
        self.assertEqual(self.txn.core_phase, TxnCorePhase.ACKED)
        self.assertEqual(self.risk.risk_phase, RiskPhase.CLOSED)
