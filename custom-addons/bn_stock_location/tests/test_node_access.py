from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestNodeAccess(TransactionCase):
    """Every user's access comes from their Branches / Sites (or All Branches /
    Sites): warehouses, locations, branches and program documents."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        plan = env['account.analytic.plan'].search([('name', '=', 'Location')], limit=1) \
            or env['account.analytic.plan'].create({'name': 'Location'})
        Account = env['account.analytic.account']
        cls.karachi = Account.create({'name': 'NA Karachi', 'plan_id': plan.id})
        cls.gulshan = Account.create({'name': 'NA Gulshan', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        cls.johar = Account.create({'name': 'NA Johar', 'plan_id': plan.id, 'parent_id': cls.karachi.id})
        cls.lahore = Account.create({'name': 'NA Lahore', 'plan_id': plan.id})
        Warehouse = env['stock.warehouse']
        cls.wh_gulshan = Warehouse.create({'name': 'NA WH Gulshan', 'code': 'NAG', 'node_id': cls.gulshan.id})
        cls.wh_johar = Warehouse.create({'name': 'NA WH Johar', 'code': 'NAJ', 'node_id': cls.johar.id})
        cls.wh_lahore = Warehouse.create({'name': 'NA WH Lahore', 'code': 'NAL', 'node_id': cls.lahore.id})
        cls.point = env['stock.location'].create({'name': 'NA Karachi Slaughter Point', 'usage': 'internal',
                                                  'analytic_account_id': cls.karachi.id})
        base = [env.ref('base.group_user').id, env.ref('stock.group_stock_user').id]

        def user(login, **vals):
            groups = base
            return env['res.users'].with_context(no_reset_password=True).create(
                dict({'name': login, 'login': login, 'groups_id': [(6, 0, groups)]}, **vals))
        cls.branch_user = user('na_branch', allowed_node_ids=[(6, 0, cls.gulshan.ids)])
        cls.city_user = user('na_city', allowed_node_ids=[(6, 0, cls.karachi.ids)])
        cls.national = user('na_national', all_nodes=True)
        cls.ours = cls.wh_gulshan | cls.wh_johar | cls.wh_lahore

    def _warehouses(self, user):
        return self.env['stock.warehouse'].with_user(user).search([('id', 'in', self.ours.ids)])

    def test_branch_user(self):
        self.assertEqual(self._warehouses(self.branch_user), self.wh_gulshan)
        self.assertIn(self.gulshan, self.branch_user.scope_analytic_account_ids)
        self.assertNotIn(self.johar, self.branch_user.scope_analytic_account_ids)
        Picking = self.env['stock.picking'].with_user(self.branch_user)
        self.assertFalse(Picking.search([('location_id', '=', self.wh_lahore.lot_stock_id.id)]))

    def test_city_user_sees_its_branches(self):
        self.assertEqual(self._warehouses(self.city_user), self.wh_gulshan | self.wh_johar)
        self.assertIn(self.point, self.city_user.scope_location_ids, "tagged location outside the warehouses")
        self.assertNotIn(self.point, self.branch_user.scope_location_ids)

    def test_national(self):
        self.assertEqual(self._warehouses(self.national), self.ours)

    def test_no_branch_site_sees_nothing(self):
        nobody = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'na nobody', 'login': 'na_nobody',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('stock.group_stock_user').id])]})
        self.assertFalse(self._warehouses(nobody), "no Branch / Site: no warehouse (not every one)")
        nobody.allowed_node_ids = self.lahore
        self.assertEqual(self._warehouses(nobody), self.wh_lahore, "rules refreshed at once")

    def test_moving_a_warehouse(self):
        self.assertEqual(self._warehouses(self.city_user), self.wh_gulshan | self.wh_johar)
        self.wh_lahore.node_id = self.johar  # cached rules are refreshed
        self.assertEqual(self._warehouses(self.city_user), self.ours)

    # ------------------------------------------------------------------
    # T6: pickers and defaults
    # ------------------------------------------------------------------
    def test_default_node_and_warehouse(self):
        Warehouse = self.env['stock.warehouse']
        self.assertEqual(self.branch_user._default_node(), self.gulshan, "the only Allowed Branch / Site")
        self.assertEqual(Warehouse.with_user(self.branch_user)._warehouse_for(), self.wh_gulshan)
        several = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'na several', 'login': 'na_several',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
            'allowed_node_ids': [(6, 0, (self.gulshan | self.lahore).ids)]})
        self.assertFalse(several._default_node(), "several, no own branch: chosen")
        self.env['hr.employee'].create({'name': 'na several', 'user_id': several.id,
                                        'analytic_account_id': self.lahore.id})
        several.invalidate_recordset()
        self.assertEqual(several._default_node(), self.lahore, "their own branch")
        self.assertEqual(Warehouse.with_user(several)._warehouse_for(), self.wh_lahore)

    def test_branch_picker(self):
        Account = self.env['account.analytic.account'].with_context(branch_scope=True)
        ours = self.karachi | self.gulshan | self.johar | self.lahore
        self.assertEqual(Account.with_user(self.city_user).search([('id', 'in', ours.ids)]),
                         self.karachi | self.gulshan | self.johar)
        self.assertEqual(Account.with_user(self.national).search([('id', 'in', ours.ids)]), ours)
        welfare_field = self.env.registry.get('welfare.line')
        if welfare_field is not None:
            self.assertTrue(self.env['welfare.line']._fields['analytic_account_id'].context.get('branch_scope'))

    def test_national_groups(self):
        """Joining a national group gives All Branches / Sites; a module's
        Administrator is not national through the Audit tier it includes."""
        Users = self.env['res.users'].with_context(no_reset_password=True)
        base = self.env.ref('base.group_user')
        accountant = Users.create({'name': 'na acc', 'login': 'na_acc', 'groups_id': [
            (6, 0, [base.id, self.env.ref('account.group_account_manager').id])]})
        self.assertTrue(accountant.all_nodes)
        auditor_group = self.env.ref('bn_welfare.group_welfare_audit', raise_if_not_found=False)
        admin_group = self.env.ref('bn_welfare.group_welfare_admin', raise_if_not_found=False)
        if auditor_group and admin_group and auditor_group in admin_group.trans_implied_ids:
            module_admin = Users.create({'name': 'na wadm', 'login': 'na_wadm', 'groups_id': [
                (6, 0, [base.id, admin_group.id])]})
            self.assertFalse(module_admin.all_nodes, "its Audit tier comes with Administrator")
            auditor = Users.create({'name': 'na aud', 'login': 'na_aud', 'groups_id': [
                (6, 0, [base.id, auditor_group.id])]})
            self.assertTrue(auditor.all_nodes, "an auditor")
        plain = Users.create({'name': 'na plain', 'login': 'na_plain', 'groups_id': [(6, 0, [base.id])]})
        self.assertFalse(plain.all_nodes)
        plain.groups_id = [(4, self.env.ref('bn_stock_location.stock_scope_unrestricted_group').id)]
        self.assertTrue(plain.all_nodes, "given a national group later")

    def test_no_access_by_creator(self):
        """No Branch / Site or analytic-scope rule of the bn modules lets a user see
        a record because they created it or are its user: the analytic account
        (Branch / Site) decides. Role rules that only narrow what a user sees
        inside their Branch / Site stay (own audit log, own requests, own POS shop,
        a doctor's prescriptions, a slip of one's own session, a box one installs)."""
        narrowing = {
            'bn_audit_trail.rule_audit_trail_log_own', 'bn_audit_trail.rule_audit_trail_log_line_own',
            'bn_material_request.material_request_rule_own', 'bn_material_request.material_request_line_rule_own',
            'bn_pos_customization.pos_order_rule', 'bn_pos_customization.pos_payment_rule',
            'bn_pos_customization.pos_session_rule', 'bn_pos_customization.pos_shop_rule',
            'bn_medical_prescription.medical_prescription_doctor_rule',
            'bn_medical_prescription.medical_prescription_doctor_group_rule',
            'bn_medical_prescription.medical_prescription_line_doctor_rule',
            'bn_medical_prescription.medical_prescription_line_doctor_group_rule',
            'bn_closing_session.pos_session_slip_own_session_rule',
            'bn_donation_box.donation_box_registration_own_city_rule',
        }
        data = self.env['ir.model.data'].search([('model', '=', 'ir.rule'), ('module', '=like', 'bn\\_%')])
        offending = []
        for xmlid in data:
            rule = self.env['ir.rule'].browse(xmlid.res_id).exists()
            name = '%s.%s' % (xmlid.module, xmlid.name)
            if rule and name not in narrowing and (
                    'create_uid' in rule.domain_force or 'user.id' in rule.domain_force):
                offending.append(name)
        self.assertFalse(offending, "rules giving access by creator / user")
        for name in narrowing:
            rule = self.env.ref(name)
            self.assertTrue(rule.groups or 'user.has_group' in rule.domain_force,
                            "%s narrows a role, it is not global for everyone" % name)

    def test_creator_outside_branch(self):
        """A user who created a document of another Branch / Site does not see it."""
        if 'livestock.requisition' not in self.env:
            self.skipTest('no program document model installed')
        Doc = self.env['livestock.requisition']
        groups = (self.env.ref('bn_livestock_slaugther.livestock_slaugther_menu_group')
                  | self.env.ref('bn_livestock_slaugther.livestock_slaugther_admin_group'))
        (self.branch_user | self.national).groups_id |= groups
        doc = Doc.with_user(self.branch_user).create({})
        self.assertEqual(doc.node_id, self.gulshan, "no location: the creator's only Branch / Site")
        self.assertTrue(Doc.with_user(self.branch_user).search([('id', '=', doc.id)]))
        doc.sudo().destination_location_id = self.wh_lahore.lot_stock_id
        self.assertEqual(doc.node_id, self.lahore)
        self.assertFalse(Doc.with_user(self.branch_user).search([('id', '=', doc.id)]))
        self.assertTrue(Doc.with_user(self.national).search([('id', '=', doc.id)]))
