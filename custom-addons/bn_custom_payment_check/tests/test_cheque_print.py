from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestChequePrint(AccountTestInvoicingCommon):
    """The first print of a cheque is open to the payment's users; a reprint
    needs the Reprint Cheque right and a reason."""

    @classmethod
    def setup_company_data(cls, company_name, chart_template=None, **kwargs):
        # Contacts are created by the Contacts right only (bn_access_right): the
        # accounting test user gets it before the companies and partners are made
        contact_group = cls.env.ref('bn_access_right.custom_contact_group', raise_if_not_found=False)
        if contact_group and contact_group not in cls.env.user.groups_id:
            cls.env.user.sudo().groups_id |= contact_group
        return super().setup_company_data(company_name, chart_template=chart_template, **kwargs)

    @classmethod
    def setUpClass(cls, chart_template_ref=None):
        super().setUpClass(chart_template_ref=chart_template_ref)
        cls.bank = cls.company_data['default_journal_bank']
        # without a document layout, printing first asks to configure one
        cls.env.company.external_report_layout_id = cls.env.ref('web.external_layout_standard')
        cls.env['bank.cheque.config'].create({'bank_name': 'Test Bank', 'journal_ids': [(6, 0, cls.bank.ids)]})
        cls.payment = cls.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': cls.partner_a.id,
            'amount': 1250.50, 'journal_id': cls.bank.id,
        })

    def test_first_print_then_reprint(self):
        action = self.payment.action_print_check()
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(self.payment.cheque_first_printed_by, self.env.user)
        self.assertIn('paisa', self.payment.check_amount_in_words)

        with self.assertRaises(AccessError):
            self.payment.action_print_check()
        self.env.user.groups_id |= self.env.ref('bn_custom_payment_check.group_cheque_reprint')
        wizard_action = self.payment.action_print_check()
        self.assertEqual(wizard_action['res_model'], 'cheque.reprint.wizard')
        wizard = self.env['cheque.reprint.wizard'].with_context(wizard_action['context']).create({'reason': 'Torn'})
        self.assertEqual(wizard.action_confirm()['type'], 'ir.actions.report')
        self.assertIn('Torn', self.payment.message_ids[0].body)

    def test_layout_needed_once_per_journal(self):
        self.env['bank.cheque.config'].create({'bank_name': 'Second', 'journal_ids': [(6, 0, self.bank.ids)]})
        with self.assertRaises(UserError):
            self.payment.action_print_check()

    def test_inbound_payments_have_no_cheque(self):
        inbound = self.env['account.payment'].create({
            'payment_type': 'inbound', 'partner_type': 'customer', 'partner_id': self.partner_a.id,
            'amount': 10, 'journal_id': self.bank.id,
        })
        with self.assertRaises(UserError):
            inbound.action_print_check()
