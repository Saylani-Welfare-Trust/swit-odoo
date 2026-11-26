from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFormAccess(TransactionCase):
    """A form opens for a user with rights on its model only: tabs and buttons
    showing other programs' records are hidden from users without their rights."""

    def _open_form(self, record, user):
        Model = record.with_user(user)
        arch = etree.fromstring(Model.get_views([(False, 'form')])['views']['form']['arch'])
        names = {node.get('name') for node in arch.iter('field')} & set(Model._fields)
        spec = {name: ({'fields': {'display_name': {}}} if Model._fields[name].relational else {})
                for name in names}
        self.env.invalidate_all()
        return Model.web_read(spec)

    def _user(self, login, groups):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'all_nodes': True,
            'groups_id': [(6, 0, [self.env.ref(g).id for g in ['base.group_user'] + groups])]})

    def test_direct_deposit_for_treasury(self):
        treasury = self._user('ffa_treasury', ['bn_pos_cheque.pos_cheque_manager_group'])
        deposit = self.env['direct.deposit'].create({
            'donor_id': self.env['res.partner'].create({'name': 'FFA Donor'}).id, 'amount': 100})
        self.assertTrue(self._open_form(deposit, treasury), "no Home Service rights needed")

    def test_contact_for_internal_user(self):
        user = self._user('ffa_internal', ['base.group_partner_manager'])
        partner = self.env['res.partner'].create({'name': 'FFA Contact'})
        self.assertTrue(self._open_form(partner, user), "no program rights needed")
