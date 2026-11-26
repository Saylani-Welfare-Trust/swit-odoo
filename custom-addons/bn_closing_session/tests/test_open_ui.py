from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOpenUi(TransactionCase):
    """A cashier opens the next session after one was closed: the check of the
    last session's journal entry must not need rights on journal entries."""

    def setUp(self):
        super().setUp()
        env = self.env
        self.config = env['pos.config'].create({'name': 'OUI Counter'})
        self.cashier = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'OUI Cashier', 'login': 'oui_cashier', 'all_nodes': True,
            'groups_id': [(6, 0, [env.ref('point_of_sale.group_pos_user').id])]})
        journal = env['account.journal'].search([('type', '=', 'general')], limit=1)
        account = env['account.account'].search([('account_type', '=', 'income')], limit=1)
        self.move = env['account.move'].create({'journal_id': journal.id, 'line_ids': [
            (0, 0, {'account_id': account.id, 'debit': 10}),
            (0, 0, {'account_id': account.id, 'credit': 10})]})
        session = env['pos.session'].create({'config_id': self.config.id, 'user_id': env.uid})
        session.write({'state': 'closed', 'move_id': self.move.id})

    def _open(self):
        self.env.invalidate_all()  # read as the cashier, not from the creator's cache
        try:
            self.config.with_user(self.cashier).open_ui()
        except AccessError as error:
            # other rights of the bare test user are not this check's concern
            self.assertNotIn('account.move', str(error), "the check needs no rights on journal entries")
            return ''
        except (UserError, ValidationError) as error:
            return str(error)
        return ''

    def test_posted_entry(self):
        self.move.action_post()
        self.assertNotIn('previous session Journal Entry', self._open())

    def test_draft_entry(self):
        self.assertIn('previous session Journal Entry', self._open())
