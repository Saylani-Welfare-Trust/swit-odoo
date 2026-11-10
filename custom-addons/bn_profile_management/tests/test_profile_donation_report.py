import io
import zipfile
from unittest.mock import patch

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
        for title, node, pages in tabs:
            self.assertIn(node.get('name'), self.partner._fields, title)
            self.assertIn('donation', [page.get('name') for page in pages], title)
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

    def _fake_data(self, partner):
        """A contact with two donation tabs, to render every part of the reports."""
        tab = lambda title, n: {
            'title': title, 'columns': ['Ref', 'Amount'], 'numeric': [False, True],
            'rows': [[('R%d' % i, 'R%d' % i), ('{:,.2f}'.format(i), float(i))] for i in range(n)],
            'totals': ['', '{:,.2f}'.format(sum(range(n)))], 'total_values': [None, float(sum(range(n)))],
            'summary_total': '{:,.2f}'.format(sum(range(n)))}
        return {'partner': partner, 'details': [('Name', partner.name, partner.name)],
                'tabs': [tab('POS Details', 60), tab('Donor Account', 2)]}

    def test_rendering_with_donation_tabs(self):
        Data = type(self.Data)
        with patch.object(Data, '_contact_data', lambda this, partner: self._fake_data(partner)):
            html = self.env['ir.actions.report']._render_qweb_html(
                'bn_profile_management.action_profile_donation_report', self.partner.ids)[0].decode()
            content, _type = self.env['ir.actions.report']._render(
                'bn_profile_management.action_profile_donation_report_xlsx', self.partner.ids)
        self.assertEqual(html.count('class="tab-page"'), 2, 'each donation tab on its own page')
        self.assertLess(html.index('POS Details - '), html.index('Donor Account - '), 'one after the other')
        self.assertIn('R59', html)
        self.assertIn('1,770.00', html, 'summary and total of the tab')
        with zipfile.ZipFile(io.BytesIO(content)) as book:
            sheets = book.read('xl/workbook.xml')
        self.assertIn(b'POS Details', sheets)
        self.assertIn(b'Donor Account', sheets)

    def test_excel(self):
        content, report_type = self.env['ir.actions.report']._render(
            'bn_profile_management.action_profile_donation_report_xlsx', self.partner.ids)
        self.assertEqual(report_type, 'xlsx')
        with zipfile.ZipFile(io.BytesIO(content)) as book:
            self.assertIn('xl/workbook.xml', book.namelist())
            self.assertIn(b'Report Donor', book.read('xl/sharedStrings.xml'))

    # ------------------------------------------------------------------
    # dynamic profiling: the contact's Profile Types decide
    # ------------------------------------------------------------------
    def _profile_type(self, name, form_fields, pages):
        Field = self.env['ir.model.fields']
        tag = self.env['res.partner.category'].create({
            'name': name, 'is_profile_type': True,
            'profile_form_field_ids': [(6, 0, Field.search([('model', '=', 'res.partner'),
                                                            ('name', 'in', form_fields)]).ids)],
            'profile_page_ids': [(6, 0, self.env['profile.management.page'].search(
                [('technical_name', 'in', pages)]).ids)],
        })
        # the administrator's order: as listed
        for position, fname in enumerate(form_fields):
            tag._profile_view_lines('form').filtered(lambda l: l.field_id.name == fname).sequence = position
        return tag

    def test_details_follow_the_profile_type(self):
        tag = self._profile_type('Report Type', ['father_name', 'surname'], ['donation'])
        partner = self.env['res.partner'].create({
            'name': 'Typed Donor', 'category_id': [(6, 0, tag.ids)], 'surname': 'Khan', 'father_name': 'Aslam',
            'nearest_land_mark': 'Not selected'})
        labels = [label for label, _text, _value in self.Data._contact_data(partner)['details']]
        father = partner._fields['father_name'].string
        surname = partner._fields['surname'].string
        self.assertIn(father, labels)
        self.assertIn(surname, labels)
        self.assertLess(labels.index(father), labels.index(surname), 'in the order chosen on the Profile Type')
        self.assertNotIn(partner._fields['nearest_land_mark'].string, labels, 'not selected by the Profile Type')

    def test_donation_tabs_only_when_the_profile_shows_them(self):
        with_page = self._profile_type('With Donations', ['surname'], ['donation'])
        without = self._profile_type('Without Donations', ['surname'], [])
        Data = self.Data
        _details, tabs = Data._layout(with_page)
        if not tabs:
            self.skipTest('no module adds a Donation tab')
        pages = tabs[0][2]
        shown = self.env['res.partner'].create({'name': 'Shown', 'category_id': [(6, 0, with_page.ids)]})
        hidden = self.env['res.partner'].create({'name': 'Hidden', 'category_id': [(6, 0, without.ids)]})
        self.assertTrue(all(Data._visible(shown, page.get('invisible')) for page in pages))
        self.assertFalse(all(Data._visible(hidden, page.get('invisible')) for page in pages))
