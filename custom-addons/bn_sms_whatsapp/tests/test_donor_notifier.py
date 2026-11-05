from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

REPORT = 'odoo.addons.base.models.ir_actions_report.IrActionsReport._render_qweb_pdf'


@tagged('post_install', '-at_install')
class TestDonorNotifier(TransactionCase):
    """Donation receipt: WhatsApp first, SMS only as the fallback."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Notifier = cls.env['bn.donor.notifier']
        cls.sent = []
        cls.record = cls.env['res.partner'].create({'name': 'Receipt record'})

    def _send(self, partner, wa_fails=False, sms_fails=False, pdf_fails=False):
        sent = []

        def fake_wa(service, mobile, link, filename):
            if wa_fails:
                raise Exception('WA gateway down')
            sent.append(('whatsapp', mobile, link))
            return True

        def fake_sms(service, mobile, message):
            if sms_fails:
                raise Exception('SMS gateway down')
            sent.append(('sms', mobile, message))
            return True

        def fake_pdf(report, report_ref, res_ids=None, data=None):
            if pdf_fails:
                raise Exception('no wkhtmltopdf')
            return b'%PDF-1.4 fake', 'pdf'

        WA = type(self.env['whatsapp.service'])
        SMS = type(self.env['sms.service'])
        with patch.object(WA, 'send_template_message', fake_wa), \
                patch.object(SMS, 'send_sms', fake_sms), patch(REPORT, fake_pdf):
            result = self.Notifier._send(self.record, partner, lambda link: 'Thanks %s' % (link or ''),
                                         report_name='bn_pos_order.pos_whatsapp_donation_receipt_template',
                                         filename='Receipt_T.pdf')
        return result, sent

    def test_whatsapp_only_when_it_works(self):
        donor = self.env['res.partner'].create({'name': 'D1', 'whatsapp': '3001234567', 'mobile': '3001234567'})
        result, sent = self._send(donor)
        self.assertEqual(result['channel'], 'whatsapp')
        self.assertEqual([s[0] for s in sent], ['whatsapp'], 'no SMS when WhatsApp worked')
        self.assertIn('access_token=', sent[0][2])

    def test_sms_when_whatsapp_fails(self):
        donor = self.env['res.partner'].create({'name': 'D2', 'whatsapp': '3001234567', 'mobile': '3001234568'})
        result, sent = self._send(donor, wa_fails=True)
        self.assertEqual((result['status'], result['channel']), ('warning', 'sms'))
        self.assertEqual([s[0] for s in sent], ['sms'])
        self.assertIn('access_token=', sent[0][2], 'the SMS link keeps its token')

    def test_sms_when_no_whatsapp_number(self):
        # a donor's WhatsApp number defaults to the mobile; cleared here
        donor = self.env['res.partner'].create({'name': 'D3', 'mobile': '3001234569'})
        donor.whatsapp = False
        result, sent = self._send(donor)
        self.assertEqual((result['status'], result['channel']), ('success', 'sms'))
        self.assertEqual([s[0] for s in sent], ['sms'])

    def test_sms_without_link_when_receipt_fails(self):
        donor = self.env['res.partner'].create({'name': 'D4', 'whatsapp': '3001234567', 'mobile': '3001234570'})
        result, sent = self._send(donor, pdf_fails=True)
        self.assertEqual(result['channel'], 'sms')
        self.assertEqual(sent, [('sms', '3001234570', 'Thanks ')])

    def test_mobile_only_donor_gets_whatsapp_first(self):
        donor = self.env['res.partner'].create({'name': 'D7', 'mobile': '3001234572'})
        result, sent = self._send(donor)
        self.assertEqual([s[0] for s in sent], ['whatsapp'])

    def test_nothing_without_numbers(self):
        donor = self.env['res.partner'].create({'name': 'D5'})
        result, sent = self._send(donor)
        self.assertEqual(result['status'], 'error')
        self.assertFalse(sent)

    def test_logged_on_the_record(self):
        donor = self.env['res.partner'].create({'name': 'D6', 'mobile': '3001234571'})
        donor.whatsapp = False
        self._send(donor)
        self.assertIn('sent by SMS', self.record.message_ids[:1].body)
