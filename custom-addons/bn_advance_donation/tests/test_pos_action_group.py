from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPosActionGroup(TransactionCase):
    """Advance Donation / POS Action: its own section of the user form, and the
    Advance Donation products are loaded in the POS of its cashiers only."""

    def test_group_in_advance_donation_section(self):
        group = self.env.ref('bn_advance_donation.advance_donation_pos_action_group')
        self.assertEqual(group.category_id, self.env.ref('bn_advance_donation.advance_donation'))
        sections = {cat for cat, _kind, groups, _ in self.env['res.groups'].get_groups_by_application()
                    if group in groups}
        self.assertEqual(sections, {group.category_id}, "shown in the Advance Donation section of the user form")

    def test_products_loaded_for_its_cashiers_only(self):
        Session = self.env['pos.session']

        def cashier(login, *groups):
            return self.env['res.users'].with_context(no_reset_password=True).create({
                'name': login, 'login': login,
                'groups_id': [(6, 0, [self.env.ref(g).id for g in ('point_of_sale.group_pos_user',) + groups])]})
        plain = cashier('adpos_plain')
        allowed = cashier('adpos_allowed', 'bn_advance_donation.advance_donation_pos_action_group')
        excluded = ('is_advance_donation', '=', False)
        self.assertIn(excluded, Session.with_user(plain)._loader_params_product_product()['search_params']['domain'])
        self.assertNotIn(excluded, Session.with_user(allowed)._loader_params_product_product()['search_params']['domain'])
