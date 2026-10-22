# -*- coding: utf-8 -*-
from psycopg2 import IntegrityError

from odoo.api import call_kw
from odoo.tests import TransactionCase, tagged
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
