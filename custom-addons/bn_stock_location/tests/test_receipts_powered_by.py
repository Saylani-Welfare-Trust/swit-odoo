import re

from odoo.modules.module import get_module_resource
from odoo.tests import TransactionCase, tagged

POWERED_BY = 'Powered by BytesNode'
# every receipt the trust gives (PDF / HTML); the ones of a module that is not installed are skipped
RECEIPTS = (
    'bn_advance_donation.action_report_advance_donation_receipt',
    'bn_advance_donation.action_report_advance_donation_line_non_cash',
    'bn_direct_deposit.report_direct_deposit_dn',
    'bn_direct_deposit.report_direct_deposit_duplicate',
    'bn_direct_deposit.report_direct_deposit_provisional',
    'bn_donation_home_service.report_donation_home_service',
    'bn_donation_in_kind.action_report_donation_in_kind',
    'bn_donation_in_kind.action_report_donation_in_kind_combined',
    'bn_donation_in_kind.action_report_donation_in_kind_whatsapp',
    'bn_key_management.donation_box_receipt_report_action',
    'bn_microfinance.microfinance_receipt_report_action',
    'bn_microfinance.security_deposit_report_action',
    'bn_pos_order.pos_donation_receipt_report',
    'bn_pos_order.pos_whatsapp_donation_receipt_report',
    'bn_welfare.action_report_welfare_collection_document',
    'bn_sadqa_e_jariya.action_report_sadqa_jariya_collection',
)


@tagged('post_install', '-at_install')
class TestReceiptsPoweredBy(TransactionCase):
    """Every receipt says 'Powered by BytesNode': the PDF receipts and the POS one."""

    def _text(self, key, seen):
        if key in seen:
            return ''
        seen.add(key)
        view = self.env['ir.ui.view'].search([('key', '=', key)], limit=1)
        if not view:
            return ''
        arch = view.get_combined_arch()
        called = (c if '.' in c else '%s.%s' % (key.split('.')[0], c)
                  for c in set(re.findall(r't-call="([\w.]+)"', arch)) if not c.startswith('web.'))
        return arch + ''.join(self._text(c, seen) for c in called)

    def test_pdf_receipts(self):
        Report = self.env['ir.actions.report']
        names = {xmlid: Report.search([('id', '=', self.env['ir.model.data']._xmlid_to_res_id(xmlid, raise_if_not_found=False) or 0)])
                 for xmlid in RECEIPTS}
        missing = [xmlid for xmlid, report in names.items()
                   if report and POWERED_BY.lower() not in self._text(report.report_name, set()).lower()]
        self.assertFalse(missing, "receipts without '%s'" % POWERED_BY)
        self.assertTrue(any(names.values()), "the receipts' report ids are known")

    def test_pos_receipt(self):
        path = get_module_resource('bn_pos_customization', 'static', 'src', 'override', 'screens',
                                   'order_receipt', 'order_receipt.xml')
        if not path:
            self.skipTest('bn_pos_customization is not here')
        with open(path) as receipt:
            self.assertIn(POWERED_BY, receipt.read())
