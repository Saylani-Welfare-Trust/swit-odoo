# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestWelfare(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ref = cls.env.ref
        cls.donee = cls.env['res.partner'].create({'name': 'Welfare Donee T'})
        cls.product = cls.env['product.product'].create({'name': 'Ration T', 'list_price': 100})
        cls.product.product_tmpl_id.is_welfare = True  # welfare lines take Is Welfare products
        cls.cash = ref('bn_welfare.disbursement_category_Cash')

        def user(login, *groups):
            return cls.env['res.users'].create({'name': login, 'login': login, 'all_nodes': True, 'groups_id': [
                (6, 0, [ref('base.group_user').id] + [ref('bn_welfare.%s' % g).id for g in groups])]})
        cls.user = user('wf_t_user', 'group_bn_welfare_user')
        cls.committee = user('wf_t_com', 'group_bn_welfare_committee')
        cls.hod = user('wf_t_hod', 'group_welfare_hod')
        cls.member = user('wf_t_mem', 'group_welfare_member')
        cls.plain = cls.env['res.users'].create({'name': 'plain', 'login': 'wf_t_plain', 'all_nodes': True, 'groups_id': [(6, 0, [ref('base.group_user').id])]})

    def _welfare(self, order_type='one_time', amount=100):
        welfare = self.env['welfare'].create({'donee_id': self.donee.id, 'order_type': order_type})
        self.env['welfare.line'].create({
            'welfare_id': welfare.id, 'product_id': self.product.id, 'quantity': 1, 'amount': amount,
            'disbursement_category_id': self.cash.id, 'collection_point': 'branch',
            'recurring_duration': '3_M' if order_type == 'recurring' else False,
            'collection_date': '2026-10-01',
        })
        for doc in ('application_form', 'frc', 'electricity_bill', 'gas_bill', 'family_cnic'):
            self.env['welfare.document.image'].create({'welfare_id': welfare.id, 'document_type': doc})
        return welfare

    def _to_hod(self, welfare):
        welfare.with_user(self.user).action_complete()
        welfare.write({'state': 'inquiry'})  # portal inquiry is external
        with self.assertRaises(AccessError):
            welfare.with_user(self.plain).action_committee_approval()
        welfare.with_user(self.user).action_committee_approval()
        welfare.committee_remarks = 'ok'
        with self.assertRaises(AccessError):
            welfare.with_user(self.user).action_move_to_hod()
        welfare.with_user(self.committee).action_move_to_hod()
        self.assertEqual(welfare.state, 'hod_approve')

    def test_workflow_and_payment_rules(self):
        welfare = self._welfare()
        with self.assertRaises(UserError):
            welfare.action_approve()  # still Draft
        self._to_hod(welfare)
        line = welfare.welfare_line_ids.filtered(lambda l: not l.is_hod)
        with self.assertRaises(ValidationError):
            line.action_disbursed()  # not approved yet
        welfare.hod_remarks = 'ok'
        with self.assertRaises(AccessError):
            welfare.with_user(self.member).action_move_to_member()
        welfare.with_user(self.hod).action_move_to_member()
        self.assertIn(welfare.state, ('approve', 'mem_approve'))
        if welfare.state == 'mem_approve':
            welfare.member_remarks = 'ok'
            welfare.with_user(self.member).action_approve()
        welfare.welfare_line_ids.filtered(lambda l: l.state == 'draft').action_disbursed()
        self.assertEqual(welfare.state, 'disbursed')
        with self.assertRaises(UserError):
            welfare.unlink()

    def test_recurring_orders_created_once(self):
        welfare = self._welfare('recurring')
        self._to_hod(welfare)
        welfare.hod_remarks = 'ok'
        welfare.with_user(self.hod).action_move_to_member()
        if welfare.state == 'mem_approve':
            welfare.member_remarks = 'ok'
            welfare.with_user(self.member).action_approve()
        welfare.with_user(self.user).action_create_recurring_order()
        self.assertEqual(welfare.state, 'recurring')
        self.assertEqual(len(welfare.welfare_recurring_line_ids), 3)
        with self.assertRaises(UserError):
            welfare.with_user(self.user).action_create_recurring_order()

    def test_delete_and_reject(self):
        draft = self._welfare()
        draft.unlink()
        welfare = self._welfare()
        self._to_hod(welfare)
        with self.assertRaises(ValidationError):
            welfare.with_user(self.hod).action_reject()  # remarks required
        welfare.rejection_remarks = 'no'
        with self.assertRaises(AccessError):
            welfare.with_user(self.user).action_reject()
        welfare.with_user(self.hod).action_reject()
        self.assertEqual(welfare.state, 'reject')

    def test_line_products_of_the_programme(self):
        """A welfare line takes an Is Welfare product of its application type's
        category, also when saved by import / RPC."""
        welfare = self.env['welfare'].create({'donee_id': self.donee.id, 'order_type': 'one_time'})
        Line = self.env['welfare.line']
        other = self.env['product.product'].create({'name': 'Not Welfare T'})
        with self.assertRaises(ValidationError):
            Line.create({'welfare_id': welfare.id, 'product_id': other.id, 'quantity': 1, 'amount': 1})
        food = self.env['product.category'].create({'name': 'WF Food'})
        app_type = self.env['disbursement.application.type'].create({'name': 'WF Food Type', 'product_category_id': food.id})
        with self.assertRaises(ValidationError):  # Is Welfare, but not in the type's category
            Line.create({'welfare_id': welfare.id, 'product_id': self.product.id, 'quantity': 1, 'amount': 1,
                         'disbursement_application_type_id': app_type.id})
        rice = self.env['product.category'].create({'name': 'WF Rice', 'parent_id': food.id})
        self.product.categ_id = rice  # sub-category of the type's category
        Line.create({'welfare_id': welfare.id, 'product_id': self.product.id, 'quantity': 1, 'amount': 1,
                     'disbursement_application_type_id': app_type.id})

    def test_approval_certificate(self):
        """Move to Member prints the Approval Certificate; it renders, can be printed
        again once approved, never before, and never empty."""
        welfare = self._welfare()
        with self.assertRaises(UserError):
            welfare.action_print_approval_certificate()  # Draft: nothing approved
        self._to_hod(welfare)
        welfare.hod_remarks = 'ok'
        action = welfare.with_user(self.hod).action_move_to_member()
        certificate = self.env.ref('bn_welfare.action_report_welfare_approval_certificate')
        self.assertEqual(action.get('report_name'), certificate.report_name)
        if welfare.state == 'mem_approve':
            welfare.member_remarks = 'ok'
            action = welfare.with_user(self.member).action_approve()
            self.assertEqual(action.get('report_name'), certificate.report_name)
            self.assertTrue(action['data']['skip_paid_hod'], "after the Final Approval, without the HOD lines paid")
        html = certificate._render_qweb_html(certificate.report_name, welfare.ids,
                                              data=action.get('data'))[0].decode()
        self.assertIn('WELFARE APPROVAL CERTIFICATE', html)
        self.assertIn(self.donee.name, html)
        again = welfare.with_user(self.user).action_print_approval_certificate()
        self.assertEqual(again.get('report_name'), certificate.report_name)

        # waiting for the Final Approval without any HOD line: nothing approved, nothing printed
        pending = self._welfare()
        pending.write({'state': 'mem_approve'})
        pending.welfare_line_ids.filtered('is_hod').unlink()
        self.assertFalse(pending._has_approved_lines())
        with self.assertRaises(UserError):
            pending.action_print_approval_certificate()

    def test_collection_document_in_print_menu(self):
        """The Final Approval prints the certificate: the collection document stays in the Print menu."""
        report = self.env.ref('bn_welfare.action_report_welfare_collection_document')
        self.assertEqual(report.binding_model_id.model, 'welfare')
