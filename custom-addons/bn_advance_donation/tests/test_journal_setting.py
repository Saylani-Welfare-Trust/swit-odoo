from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAdvanceDonationJournal(TransactionCase):

    def test_configured_journal_is_used(self):
        company = self.env.company
        journal = self.env['account.journal'].create({
            'name': 'AD Bank', 'code': 'ADBK', 'type': 'bank', 'company_id': company.id})
        company.advance_donation_journal_id = journal
        self.assertEqual(company._get_advance_donation_journal(), journal)

    def test_missing_or_archived_journal_is_refused(self):
        company = self.env.company
        company.advance_donation_journal_id = False
        with self.assertRaises(UserError):
            company._get_advance_donation_journal()
        journal = self.env['account.journal'].create({
            'name': 'AD Bank 2', 'code': 'ADB2', 'type': 'bank', 'company_id': company.id})
        company.advance_donation_journal_id = journal
        journal.active = False
        with self.assertRaises(UserError):
            company._get_advance_donation_journal()

    def test_upgrade_keeps_first_bank_journal(self):
        company = self.env.company
        company.advance_donation_journal_id = False
        first = self.env['account.journal'].search(
            [('type', '=', 'bank'), ('company_id', '=', company.id)], order='sequence, id', limit=1)
        self.env['res.company']._set_default_advance_donation_journal()
        self.assertEqual(company.advance_donation_journal_id, first)
