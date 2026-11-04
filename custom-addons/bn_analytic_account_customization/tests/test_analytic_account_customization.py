# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAnalyticAccountCustomization(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        option = cls.env['location.option'].create({'name': 'Branch'})
        cls.plan = cls.env['account.analytic.plan'].create({'name': 'Branches'})
        cls.other_plan = cls.env['account.analytic.plan'].create({'name': 'Projects'})
        Account = cls.env['account.analytic.account']
        cls.branch_x = Account.create({'name': 'Branch X', 'plan_id': cls.plan.id, 'location_option_id': option.id})
        cls.branch_y = Account.create({'name': 'Branch Y', 'plan_id': cls.plan.id, 'location_option_id': option.id})
        cls.project = Account.create({'name': 'Project P', 'plan_id': cls.other_plan.id})
        groups = [cls.env.ref('base.group_user').id, cls.env.ref('account.group_account_invoice').id,
                  cls.env.ref('analytic.group_analytic_accounting').id]

        def user(login, branch, cnic):
            u = cls.env['res.users'].create({'name': login, 'login': login, 'groups_id': [(6, 0, groups)]})
            cls.env['hr.employee'].create({'name': login, 'user_id': u.id, 'cnic_no': cnic,
                                           'analytic_account_id': branch.id if branch else False})
            return u
        cls.user_x = user('ana_x', cls.branch_x, '42101-0000001-1')
        cls.user_y = user('ana_y', cls.branch_y, '42101-0000002-1')
        cls.user_none = user('ana_none', None, '42101-0000003-1')
        cls.product = cls.env['product.product'].create({'name': 'Analytic Service', 'type': 'service'})
        cls.other_product = cls.env['product.product'].create({'name': 'Other Service', 'type': 'service'})
        cls.partner = cls.env['res.partner'].create({'name': 'Analytic Customer'})
        cls.Model = cls.env['account.analytic.distribution.model']

    def _distribution(self, user, product=None, partner=None):
        move = self.env['account.move'].with_user(user).create({
            'move_type': 'out_invoice', 'partner_id': (partner or self.partner).id,
            'invoice_line_ids': [Command.create({'product_id': (product or self.product).id, 'quantity': 1, 'price_unit': 10})]})
        return move.invoice_line_ids.analytic_distribution or {}

    def test_branch_model_applies_to_lines_with_products(self):
        self.Model.create({'analytic_account_id': self.branch_x.id, 'analytic_distribution': {str(self.branch_x.id): 100}})
        self.assertEqual(self._distribution(self.user_x), {str(self.branch_x.id): 100})
        self.assertEqual(self._distribution(self.user_y), {}, 'another branch')
        self.assertEqual(self._distribution(self.user_none), {}, 'user without branch')

    def test_conditions_that_do_not_match_reject_the_model(self):
        other_partner = self.env['res.partner'].create({'name': 'Someone else'})
        self.Model.create({'partner_id': self.partner.id, 'analytic_distribution': {str(self.project.id): 100}})
        self.Model.create({'product_id': [(6, 0, [self.product.id])], 'analytic_distribution': {str(self.branch_y.id): 100}})
        self.assertEqual(self._distribution(self.user_none, partner=other_partner, product=self.other_product), {})
        self.assertEqual(self._distribution(self.user_none, partner=other_partner, product=self.product),
                         {str(self.branch_y.id): 100})

    def test_change_branch_on_model_form(self):
        with Form(self.Model) as form:
            form.analytic_distribution = {str(self.project.id): 100}
            form.analytic_account_id = self.branch_y
            self.assertEqual(form.analytic_distribution, {'%s,%s' % (self.branch_y.id, self.project.id): 100})
            form.analytic_account_id = self.branch_x
            self.assertEqual(form.analytic_distribution, {'%s,%s' % (self.branch_x.id, self.project.id): 100})

    def _invoice(self, distribution, second_distribution=None):
        lines = [Command.create({'product_id': self.product.id, 'quantity': 1, 'price_unit': 100,
                                 'analytic_distribution': distribution})]
        if second_distribution is not None:
            lines.append(Command.create({'product_id': self.other_product.id, 'quantity': 1, 'price_unit': 50,
                                         'analytic_distribution': second_distribution}))
        move = self.env['account.move'].create({'move_type': 'out_invoice', 'partner_id': self.partner.id,
                                                'invoice_line_ids': lines})
        if second_distribution is False:
            move.invoice_line_ids[1:].analytic_distribution = False
        return move

    def test_invoice_with_analytic_can_be_posted(self):
        move = self._invoice({str(self.branch_x.id): 100})
        move.action_post()
        self.assertEqual(move.state, 'posted')

    def test_partially_tagged_invoice_is_refused(self):
        move = self._invoice({str(self.branch_x.id): 100}, False)
        with self.assertRaisesRegex(ValidationError, 'income / expense'):
            move.action_post()

    def test_batch_posting_checks_each_move(self):
        tagged_move = self._invoice({str(self.branch_x.id): 100})
        untagged = self._invoice(False)
        untagged.invoice_line_ids.analytic_distribution = False
        (tagged_move | untagged).action_post()
        self.assertEqual(set((tagged_move | untagged).mapped('state')), {'posted'})

    def test_employee_cnic(self):
        employee = self.user_x.employee_id
        with Form(employee) as form:
            form.cnic_no = '42101-0000001-1'  # its own CNIC again
        with self.assertRaises(ValidationError):
            self.env['hr.employee'].create({'name': 'Duplicate', 'cnic_no': '42101-0000001-1'})
        clerk = self.env['res.users'].create({'name': 'Clerk', 'login': 'ana_clerk',
                                              'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        public = self.env['hr.employee.public'].with_user(clerk).browse(employee.id)
        self.assertNotIn('cnic_no', public._fields)
        self.assertEqual(public.analytic_account_id, self.branch_x)
        with self.assertRaises(AccessError):
            employee.with_user(clerk).read(['cnic_no'])

    def test_root_group_shows_menu(self):
        menu = self.env.ref('bn_analytic_account_customization.analytical_accounting_menu')
        root = self.env.ref('bn_analytic_account_customization.analytic_account_customization_root_group')
        self.assertIn(root, menu.groups_id)
        for xmlid in ('user', 'audit', 'manager', 'admin'):
            group = self.env.ref('bn_analytic_account_customization.analytic_account_customization_%s_group' % xmlid)
            self.assertIn(root, group.trans_implied_ids, xmlid)

    def test_reference_data_readable_by_all_employees(self):
        """Sub Zone / Location Option are picked on donation box, key bunch and
        rider screens by people outside this module's groups."""
        zone = self.env['sub.zone'].create({'name': 'SZ', 'analytic_account_id': self.branch_x.id})
        clerk = self.env['res.users'].create({'name': 'Clerk 2', 'login': 'ana_clerk2',
                                              'groups_id': [(6, 0, [self.env.ref('base.group_user').id])]})
        self.assertEqual(self.env['sub.zone'].with_user(clerk).name_search('SZ')[0][0], zone.id)
        self.env['location.option'].with_user(clerk).search([])
        with self.assertRaises(AccessError):
            self.env['sub.zone'].with_user(clerk).create({'name': 'Not allowed'})
