# -*- coding: utf-8 -*-
import base64
import io
from unittest.mock import patch

import openpyxl

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.bn_import_donation.wizards.api_donaiton_wizard import APIDonationWizard

HEADERS = ['Transaction ID', 'Name', 'Cell Number', 'CNIC No.', 'Email', 'Date', 'Amount', 'Product', 'Reference']


@tagged('post_install', '-at_install')
class TestImportDonation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        company = env.company
        Account = env['account.account']
        cls.income = Account.search([('account_type', '=', 'income'), ('company_id', '=', company.id)], limit=1)
        cls.bank = Account.search([('account_type', '=', 'asset_cash'), ('company_id', '=', company.id)], limit=1)
        cls.fees = Account.search([('account_type', '=', 'expense'), ('company_id', '=', company.id)], limit=1)
        if not env['account.journal'].search([('type', '=', 'bank'), ('company_id', '=', company.id)], limit=1):
            env['account.journal'].create({'name': 'Test Bank', 'code': 'TBNK', 'type': 'bank'})
        Product = env['product.product']
        cls.zakat = Product.create({'name': 'Zakat T', 'type': 'service',
                                    'property_account_income_id': cls.income.id})
        cls.no_income = Product.create({'name': 'No Income T', 'type': 'service'})
        HeaderType = env['header.type']
        header_types = {name: HeaderType.search([('name', '=', name)], limit=1) or HeaderType.create({'name': name})
                        for name in HEADERS}
        cls.gateway = env['gateway.config'].create({
            'name': 'Test Gateway', 'type': 'gateway', 'account_id': cls.bank.id,
            # Position -1: the column is found by its header in the file.
            'gateway_config_header_ids': [(0, 0, {'name': name, 'header_type_id': header_types[name].id, 'position': -1})
                                          for name in HEADERS],
            'gateway_config_line_ids': [(0, 0, {'name': 'Zakat', 'product_id': cls.zakat.id}),
                                        (0, 0, {'name': 'Sadqa', 'product_id': cls.no_income.id})]})
        cls.existing = env['res.partner'].create({'name': 'Existing Ali', 'mobile': '3001112222'})

        def user(login, group):
            return env['res.users'].create({'name': login, 'login': login, 'groups_id': [
                (6, 0, [env.ref('base.group_user').id, env.ref('bn_import_donation.%s' % group).id])]})
        cls.user = user('import_user_t', 'import_donation_user_group')
        cls.manager = user('import_manager_t', 'import_donation_manager_group')

    def _file(self, rows):
        workbook = openpyxl.Workbook()
        workbook.active.append(HEADERS)
        for row in rows:
            workbook.active.append(list(row))
        buffer = io.BytesIO()
        workbook.save(buffer)
        return base64.b64encode(buffer.getvalue())

    def _batch(self, rows, name='Batch'):
        return self.env['import.donation'].with_user(self.user).create({
            'name': name, 'gateway_config_id': self.gateway.id, 'import_file': self._file(rows)})

    ROWS = [
        (70001, 'Ahmed Khan', '03001234567', 4210112345671, '', '2026-10-01', 1000, 'Zakat', 'r1'),
        (70002, 'Ahmed Khan', '+92 300 1234567', None, None, '2026-10-01', 500, 'Zakat', ''),
        (70002, 'Duplicate', '3009999999', None, None, '2026-10-01', 50, 'Zakat', ''),
        (70003, 'Zero', '3008888888', None, None, '2026-10-01', 0, 'Zakat', ''),
        (70004, 'Unmapped', '3007777777', None, None, '2026-10-01', 10, 'Fitrana', ''),
        (70005, 'Bad Mobile', '0300-12', None, None, '2026-10-01', 10, 'Zakat', ''),
        (70006, 'Ali', '03001112222', None, None, '2026-10-01', 70, 'Zakat', ''),
        (70007, 'Existing Ali', '3005550000', None, None, '2026-10-01', 80, 'Zakat', ''),
        (70008, 'No Income', '3004440000', None, None, '2026-10-01', 90, 'Sadqa', ''),
    ]

    def test_validate_classifies_every_row(self):
        batch = self._batch(self.ROWS)
        batch.action_validate_excel_file()
        valid = {line.transaction_id: line for line in batch.valid_import_donation_ids}
        invalid = {line.transaction_id + line.donor_student_name: line.reason for line in batch.invalid_import_donation_ids}
        self.assertEqual(set(valid), {'70001', '70002', '70006', '70007'})
        self.assertEqual(valid['70001'].mobile, '3001234567')
        self.assertEqual(valid['70001'].cnic_no, '42101-1234567-1')
        self.assertEqual(valid['70002'].mobile, '3001234567')
        self.assertIn('more than once', invalid['70002Duplicate'])
        self.assertIn('greater than zero', invalid['70003Zero'])
        self.assertIn('not mapped', invalid['70004Unmapped'])
        self.assertIn('10 digit', invalid['70005Bad Mobile'])
        self.assertIn('Income Account', invalid['70008No Income'])

    def test_upload_matches_donors_without_names(self):
        batch = self._batch(self.ROWS)
        batch.action_validate_excel_file()
        batch.action_upload()
        donors = {d.transaction_id: d.donor_id for d in batch.donation_ids}
        self.assertEqual(donors['70001'], donors['70002'], 'same mobile = same donor')
        self.assertEqual(donors['70006'], self.existing, 'existing contact reused by mobile')
        self.assertNotEqual(donors['70007'], self.existing, 'same name, other mobile: another person')
        self.assertEqual(donors['70001'].state, 'draft')

    def test_confirm_reset_and_reimport(self):
        batch = self._batch(self.ROWS)
        batch.action_validate_excel_file()
        batch.action_upload()
        with self.assertRaises(UserError):
            batch.action_confirm()  # User: Manager required
        # Reset removes the donations, so the file can be validated again.
        batch.action_draft()
        self.assertFalse(batch.donation_ids)
        batch.action_validate_excel_file()
        self.assertEqual(len(batch.valid_import_donation_ids), 4)
        batch.action_upload()

        managed = batch.with_user(self.manager)
        managed.action_confirm()
        move = managed.journal_entry_id
        self.assertEqual(move.state, 'draft')
        self.assertAlmostEqual(sum(move.line_ids.mapped('debit')), 1650)
        self.assertAlmostEqual(sum(move.line_ids.mapped('credit')), 1650)
        self.assertEqual(set(managed.donation_ids.mapped('state')), {'posted'})
        with self.assertRaises(ValidationError):
            managed.action_draft()

        again = self._batch(self.ROWS, 'Again')
        again.action_validate_excel_file()
        self.assertFalse(again.valid_import_donation_ids)
        self.assertTrue(any('Already imported' in r for r in again.invalid_import_donation_ids.mapped('reason')))

    def test_approve_corrected_row_after_upload(self):
        batch = self._batch(self.ROWS)
        batch.action_validate_excel_file()
        batch.action_upload()
        row = batch.invalid_import_donation_ids.filtered(lambda l: l.transaction_id == '70005').with_user(self.manager)
        row.write({'mobile': '3006660000'})
        row.action_approve()
        self.assertTrue(row.hide_button)
        self.assertTrue(batch.donation_ids.filtered(lambda d: d.transaction_id == '70005'))

        still_bad = batch.invalid_import_donation_ids.filtered(lambda l: l.transaction_id == '70004').with_user(self.manager)
        still_bad.action_approve()
        self.assertFalse(still_bad.hide_button)
        self.assertIn('not mapped', still_bad.reason)

    # ------------------------------------------------------------------
    # Website API
    # ------------------------------------------------------------------
    def _api_setup(self):
        currency = self.env.company.currency_id
        gateway = self.env['gateway.config'].search([('name', '=', 'Web API')], limit=1)
        if gateway:
            gateway.name = 'Web API (before test)'
        self.env['gateway.config'].create({
            'name': 'Web API', 'type': 'api', 'bank_charges_account_id': self.fees.id,
            'gateway_config_currency_ids': [(0, 0, {'currency_id': currency.id, 'account_id': self.bank.id})],
            'gateway_config_line_ids': [(0, 0, {'name': 'zakatgeneralone-time', 'product_id': self.zakat.id})]})
        self.env.company.sudo().write({'url': 'https://example.test', 'client_id': 'id', 'client_secret': 'secret'})
        return currency

    @staticmethod
    def _donation(_id, currency, total, charges, items, donor, status='success'):
        return {'_id': _id, 'status': status, 'currency': currency, 'total_amount': total,
                'bank_charges': charges, 'items': items, 'donor_details': donor,
                'createdAt': '2026-10-20T10:00:00Z', 'updatedAt': '2026-10-20T10:00:00Z'}

    @staticmethod
    def _item(name, total):
        return {'donationType': 'zakat', 'item': {'en': {'name': name}}, 'type': {'en': {'name': 'One-time'}},
                'total': total, 'qty': 1}

    def test_api_fetch_books_gross_income_and_charges(self):
        currency = self._api_setup()
        name = currency.name
        pages = {1: [
            self._donation('T1', name, 1000, 30, [self._item('General', 1000)],
                           {'name': 'Api Donor', 'phone': '+923001234567', 'email': 'a@x.pk'}),
            self._donation('T2', name, 700, 0, [self._item('General', 500), self._item('Unknown', 200)],
                           {'name': 'Partial', 'phone': '3115556667'}),
            self._donation('T3', name, 99, 0, [self._item('General', 99)], {'name': 'Failed'}, status='failed'),
            self._donation('T4', 'XYZ', 50, 0, [self._item('General', 50)], {'name': 'Unknown currency'}),
        ]}

        def fake(wizard, *args, override_payload=None, **kwargs):
            return pages.get(override_payload['page'], [])

        with patch.object(APIDonationWizard, '_fetch_donations_from_api', fake):
            # Cron: called on the empty model, without dates.
            self.env['api.donation.wizard'].action_fetch_donation()

        donations = {d.import_id: d for d in self.env['api.donation'].search([('import_id', 'in', ['T1', 'T2', 'T3', 'T4'])])}
        self.assertNotIn('T3', donations, 'unsuccessful payments are not stored')
        self.assertEqual(donations['T1'].journal_status, 'in_entry')
        self.assertEqual(donations['T2'].journal_status, 'partial')
        self.assertEqual(donations['T4'].journal_status, 'not_in_entry')

        move = donations['T1'].fetch_history_id.journal_entry_id
        lines = {(line.account_id, line.debit > 0): round(line.balance, 2) for line in move.line_ids}
        self.assertEqual(lines[(self.income, False)], -1500.0)       # gross: 1000 + 500
        self.assertEqual(lines[(self.fees, True)], 30.0)             # bank charges
        self.assertEqual(lines[(self.bank, True)], 1470.0)           # gateway: gross - charges
        self.assertEqual(move.state, 'draft')

    def test_api_partner_without_email_is_not_matched_to_other_contact(self):
        self._api_setup()
        stranger = self.env['res.partner'].create({'name': 'No Email Stranger', 'mobile': '3112223334'})
        donation = self.env['api.donation'].create({'import_id': 'P1', 'name': 'New Donor', 'phone': '3001239999',
                                                    'email': False, 'country': 'PK'})
        donation.action_create_partners_for_selected()
        self.assertEqual(donation.partner_creation_status, 'created')
        self.assertNotEqual(donation.donor_id, stranger)
        self.assertEqual(donation.donor_id.mobile, '3001239999')

    def test_api_credentials_hidden_from_managers(self):
        self._api_setup()
        with self.assertRaises(Exception):
            self.env.company.with_user(self.manager).read(['client_secret'])
