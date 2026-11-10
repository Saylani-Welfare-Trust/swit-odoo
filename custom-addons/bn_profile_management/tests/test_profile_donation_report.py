import io
import zipfile

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProfileDonationReport(TransactionCase):
    """Contact details and every Donation tab of the profile form, in PDF
    (HTML checked here) and Excel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Report Donor', 'mobile': '3001231234', 'street': 'Street 9', 'city': 'Karachi'})
        cls.Data = cls.env['profile.donation.report.data']

    def test_layout_follows_the_form(self):
        details, tabs = self.Data._layout()
        names = {node.get('name') for node in details}
        self.assertIn('name', names)
        self.assertIn('mobile', names)
        for title, node in tabs:
            self.assertIn(node.get('name'), self.partner._fields, title)
            self.assertIsNotNone(node.find('tree'), title)

    def test_contact_data(self):
        data = self.Data._contact_data(self.partner)
        labels = dict((label, text) for label, text, _value in data['details'])
        self.assertEqual(labels.get('Mobile'), '3001231234')
        # the profile's own rules decide which fields show, as on the form
        city_shown = ',city,' in (self.partner.profile_visible_form_field_names or '')
        self.assertEqual(labels.get('City') == 'Karachi', city_shown)
        # only tabs that have records
        for tab in data['tabs']:
            self.assertTrue(tab['rows'], tab['title'])
            self.assertEqual(len(tab['columns']), len(tab['rows'][0]))

    def test_each_tab_on_its_own_page(self):
        html = self.env['ir.actions.report']._render_qweb_html(
            'bn_profile_management.action_profile_donation_report', self.partner.ids)[0].decode()
        self.assertIn('Report Donor', html)
        tabs = self.Data._contact_data(self.partner)['tabs']
        self.assertEqual(html.count('class="tab-page"'), len(tabs))

    def test_excel(self):
        content, report_type = self.env['ir.actions.report']._render(
            'bn_profile_management.action_profile_donation_report_xlsx', self.partner.ids)
        self.assertEqual(report_type, 'xlsx')
        with zipfile.ZipFile(io.BytesIO(content)) as book:
            self.assertIn('xl/workbook.xml', book.namelist())
            self.assertIn(b'Report Donor', book.read('xl/sharedStrings.xml'))
