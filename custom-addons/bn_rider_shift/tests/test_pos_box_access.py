from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPosBoxAccess(TransactionCase):
    """The Donation Box button of the POS and its server calls belong to
    Donation Box / POS Action (or a Donation Box Manager)."""

    def _user(self, login, *groups):
        return self.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login,
            'groups_id': [(6, 0, [self.env.ref(g).id for g in ('base.group_user', 'point_of_sale.group_pos_user') + groups])]})

    def test_group_in_donation_box_section(self):
        group = self.env.ref('bn_donation_box.donation_box_pos_action_group')
        self.assertEqual(group.category_id, self.env.ref('bn_donation_box.module_donation_box'))
        sections = {cat for cat, _kind, groups, _ in self.env['res.groups'].get_groups_by_application()
                    if group in groups}
        self.assertEqual(sections, {group.category_id})

    def test_only_pos_action_users(self):
        plain = self._user('box_plain')
        cashier = self._user('box_cashier', 'bn_donation_box.donation_box_pos_action_group')
        manager = self._user('box_manager', 'bn_donation_box.donation_box_manager_group')
        for model, method, args in (('rider.collection', 'get_rider_collection', ()),
                                    ('key.issuance', 'set_donation_amount', ({},))):
            with self.assertRaises(AccessError):
                getattr(self.env[model].with_user(plain), method)(*args)
            for user in (cashier, manager):
                result = getattr(self.env[model].with_user(user), method)(*args)
                self.assertIn('status', result, "%s answers %s" % (method, user.login))
