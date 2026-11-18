from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestIbftBatch(AccountTestInvoicingCommon):
    """Confirm IBFT gives the selected payments one batch number; a batch is
    reprinted only by an IBFT Reprint user, with a reason."""

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
        cls.env.user.groups_id |= cls.env.ref('account.group_account_invoice')
        cls.partner_a.bank_ids = [(0, 0, {'acc_number': 'PK00TEST0001', 'acc_holder_name': 'Vendor A'})]

    def _payment(self, amount=100):
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound', 'partner_type': 'supplier', 'partner_id': self.partner_a.id,
            'amount': amount, 'journal_id': self.company_data['default_journal_bank'].id,
        })
        payment.action_post()
        return payment

    def test_batch_and_reprint(self):
        payments = self._payment() | self._payment(250)
        action = payments.action_confirm_ibft()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        batch = payments[0].ibft_batch_no
        self.assertTrue(batch.startswith('IBFT/'))
        self.assertEqual(set(payments.mapped('ibft_batch_no')), {batch}, 'one batch for the selection')
        self.assertEqual(set(payments.mapped('ibft_status')), {'success'})

        # reprint needs the IBFT Reprint right
        with self.assertRaises(AccessError):
            payments.action_confirm_ibft()
        self.env.user.groups_id |= self.env.ref('bn_payment_customization.group_ibft_reprint')
        wizard_action = payments.action_confirm_ibft()
        self.assertEqual(wizard_action['res_model'], 'ibft.reprint.wizard')
        wizard = self.env['ibft.reprint.wizard'].with_context(wizard_action['context']).create({'reason': 'Bank lost the file'})
        wizard.action_confirm()
        self.assertEqual(set(payments.mapped('ibft_batch_no')), {batch}, 'the reprint keeps the batch number')
        self.assertIn('Bank lost the file', payments[0].message_ids[0].body)

    def test_one_batch_per_reprint(self):
        first, second = self._payment(), self._payment()
        first.action_confirm_ibft()
        second.action_confirm_ibft()
        self.assertNotEqual(first.ibft_batch_no, second.ibft_batch_no)
        with self.assertRaises(UserError):
            (first | second).action_confirm_ibft()
