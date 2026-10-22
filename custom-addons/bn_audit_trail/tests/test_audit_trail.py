# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo.api import call_kw
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError
from odoo.tools import mute_logger

from odoo.addons.bn_audit_trail.models.audit_log import MASK


@tagged('post_install', '-at_install')
class TestAuditTrail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Log = cls.env['audit.trail.log'].sudo()

    def setUp(self):
        super().setUp()
        self.env.transaction._audit_read_seen = set()

    def _new_logs(self, start, domain=()):
        return self.Log.search([('id', '>', start)] + list(domain), order='id')

    def _last_id(self):
        return self.Log.search([], order='id desc', limit=1).id or 0

    def test_web_client_calls(self):
        """The overridden read methods must keep their RPC signature: the
        web client goes through call_kw(), which relies on @api.model."""
        Partner = self.env['res.partner']
        partner = Partner.create({'name': 'Audit RPC'})
        result = call_kw(Partner, 'web_search_read', [], {
            'domain': [('id', '=', partner.id)], 'specification': {'display_name': {}}, 'limit': 1})
        self.assertEqual(result['records'][0]['id'], partner.id)
        result = call_kw(Partner, 'web_search_read', [[('id', '=', partner.id)], {'display_name': {}}], {})
        self.assertEqual(result['length'], 1)
        result = call_kw(Partner, 'web_read', [[partner.id]], {'specification': {'display_name': {}}})
        self.assertEqual(result[0]['id'], partner.id)
        result = call_kw(Partner, 'read', [[partner.id], ['name']], {})
        self.assertEqual(result[0]['name'], 'Audit RPC')
        new_id = call_kw(Partner, 'create', [{'name': 'Audit RPC 2'}], {})
        self.assertTrue(call_kw(Partner, 'write', [[new_id], {'name': 'Audit RPC 3'}], {}))
        self.assertTrue(call_kw(Partner, 'unlink', [[new_id]], {}))

    def test_secrets_are_masked(self):
        user = self.env['res.users'].create({'name': 'Audit U', 'login': 'audit_u', 'password': 'Plain#Create1'})
        user.password = 'Plain#Write2'
        lines = self.Log.search([('model_name', '=', 'res.users'), ('res_id', '=', user.id)]).line_ids
        password_lines = lines.filtered(lambda l: l.field_name == 'password')
        self.assertEqual(len(password_lines), 2, "Both password changes are recorded")
        self.assertEqual(set(password_lines.mapped('new_value')), {MASK})
        stored = ' '.join((l.old_value or '') + (l.new_value or '') for l in self.Log.search([]).line_ids)
        self.assertNotIn('Plain#', stored)

    def test_constraint_error_reaches_caller(self):
        self.env['res.users'].create({'name': 'Audit A', 'login': 'audit_a'})
        other = self.env['res.users'].create({'name': 'Audit B', 'login': 'audit_b'})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            other.write({'login': 'audit_a'})
            self.env.flush_all()

    def test_precommit_hooks_not_run_early(self):
        partner = self.env['res.partner'].create({'name': 'Audit P'})
        ran = []
        self.env.cr.precommit.add(lambda: ran.append(True))
        partner.read(['name'])
        partner.write({'comment': 'changed'})
        self.assertFalse(ran)
        self.env.cr.precommit.clear()

    def test_x2many_after_value(self):
        partner = self.env['res.partner'].create({'name': 'Audit P'})
        tag = self.env['res.partner.category'].create({'name': 'Audit Tag'})
        partner.write({'category_id': [(4, tag.id)]})
        line = self.Log.search([('model_name', '=', 'res.partner'), ('res_id', '=', partner.id),
                                ('method', '=', 'write')]).line_ids.filtered(lambda l: l.field_name == 'category_id')
        self.assertEqual(line.new_value, 'Audit Tag')

    def test_nested_create_is_a_sub_operation(self):
        start = self._last_id()
        company = self.env['res.partner'].create({
            'name': 'Audit Co', 'is_company': True,
            'child_ids': [(0, 0, {'name': 'Audit Contact'})],
        })
        logs = self._new_logs(start, [('method', '=', 'create')])
        master = logs.filtered(lambda l: l.res_id == company.id)
        contact = logs - master
        self.assertEqual(len(master), 1)
        self.assertFalse(master.parent_id)
        self.assertEqual(contact.parent_id, master)
        self.assertEqual(len(set(logs.mapped('operation_ref'))), 1)

    def test_form_read_groups_linked_records(self):
        company = self.env['res.partner'].create({'name': 'Audit Co', 'is_company': True})
        contact = self.env['res.partner'].create({'name': 'Audit Contact', 'parent_id': company.id})
        self.env.transaction._audit_read_seen = set()
        start = self._last_id()
        contact.web_read({'name': {}, 'parent_id': {'fields': {'display_name': {}, 'email': {}}}})
        logs = self._new_logs(start, [('method', '=', 'read')])
        master = logs.filtered(lambda l: not l.parent_id)
        self.assertEqual(master.res_id, contact.id)
        self.assertEqual(master.record_name, contact.display_name)
        self.assertIn(company.id, master.child_ids.mapped('res_id'))

    def test_exclusion_changes_are_logged(self):
        exclusion = self.env['audit.trail.exclusion'].create({
            'model_id': self.env['ir.model']._get_id('res.partner.category')})
        exclusion.unlink()
        methods = self.Log.search([('model_name', '=', 'audit.trail.exclusion')]).mapped('method')
        self.assertIn('create', methods)
        self.assertIn('unlink', methods)
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'):
            self.env['audit.trail.exclusion'].create({
                'model_id': self.env['ir.model']._get_id('audit.trail.log')})

    def test_excluded_model_is_not_logged(self):
        self.env['audit.trail.exclusion'].create({
            'model_id': self.env['ir.model']._get_id('res.partner.category')})
        start = self._last_id()
        self.env['res.partner.category'].create({'name': 'Not Logged'})
        self.assertFalse(self._new_logs(start, [('model_name', '=', 'res.partner.category')]))

    def test_purge_leaves_a_trace(self):
        partner = self.env['res.partner'].create({'name': 'Audit P'})
        logs = self.Log.search([('model_name', '=', 'res.partner'), ('res_id', '=', partner.id)])
        # Sub-operations are deleted with their master entry and counted too.
        count = len(self.Log.search([('parent_id', 'child_of', logs.ids)]))
        logs.unlink()
        purge = self.Log.search([('record_name', '=', 'Audit log purge')], order='id desc', limit=1)
        self.assertTrue(purge)
        self.assertIn('Deleted %s audit log entries' % count, purge.summary)


@tagged('post_install', '-at_install')
class TestAuditTrailAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group = lambda x: cls.env.ref('bn_audit_trail.group_audit_trail_' + x)
        base = cls.env.ref('base.group_user')

        def user(login, name):
            return cls.env['res.users'].create({'name': login, 'login': login,
                                               'groups_id': [(6, 0, [base.id, group(name).id])]})
        cls.user = user('audit_t_user', 'user')
        cls.auditor = user('audit_t_audit', 'viewer')
        cls.manager = user('audit_t_manager', 'manager')
        cls.admin = user('audit_t_admin', 'admin')
        cls.Log = cls.env['audit.trail.log']
        partner = cls.env['res.partner'].create({'name': 'Access Test'})
        cls.own = cls.Log.sudo().create({'user_id': cls.user.id, 'model_name': 'res.partner', 'res_id': partner.id,
                                         'method': 'write', 'summary': 'own entry'})
        cls.other = cls.Log.sudo().create({'user_id': cls.admin.id, 'model_name': 'res.partner', 'res_id': partner.id,
                                           'method': 'write', 'summary': 'other entry'})

    def _visible(self, user):
        return self.Log.with_user(user).search([('id', 'in', (self.own | self.other).ids)])

    def test_user_sees_only_own_entries(self):
        self.assertEqual(self._visible(self.user), self.own)

    def test_audit_and_above_see_everything(self):
        for user in (self.auditor, self.manager, self.admin):
            self.assertEqual(self._visible(user), self.own | self.other, user.login)

    def test_only_admin_can_purge(self):
        for user in (self.user, self.auditor, self.manager):
            with self.assertRaises(AccessError):
                self.other.with_user(user).unlink()
        self.other.with_user(self.admin).unlink()

    def test_only_manager_and_admin_manage_exclusions(self):
        model_id = self.env['ir.model']._get_id('res.partner.category')
        Exclusion = self.env['audit.trail.exclusion']
        self.assertFalse(Exclusion.with_user(self.auditor).search([]) and False)  # can read
        for user in (self.user, self.auditor):
            with self.assertRaises(AccessError):
                Exclusion.with_user(user).create({'model_id': model_id})
        Exclusion.with_user(self.manager).create({'model_id': model_id}).unlink()

    def test_viewing_the_trail_is_logged(self):
        Log = self.Log.with_user(self.auditor)
        before = self.Log.sudo().search_count([('model_name', '=', 'audit.trail.log'), ('user_id', '=', self.auditor.id)])
        call_kw(Log, 'web_search_read', [], {'domain': [], 'specification': {'summary': {}}, 'limit': 10})
        call_kw(Log, 'web_read', [[self.other.id]], {'specification': {
            'summary': {}, 'child_ids': {'fields': {'summary': {}}}, 'line_ids': {'fields': {'field_name': {}}}}})
        views = self.Log.sudo().search([('model_name', '=', 'audit.trail.log'), ('user_id', '=', self.auditor.id)], order='id')
        self.assertEqual(len(views) - before, 2)
        self.assertIn('Viewed the audit trail list', views[-2].summary)
        self.assertEqual(views[-1].res_id, self.other.id)
