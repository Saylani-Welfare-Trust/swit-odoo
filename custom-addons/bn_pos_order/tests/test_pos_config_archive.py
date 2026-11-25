# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestPosConfigArchive(TransactionCase):
    """Archiving and restoring a shop both need the Archive and Unarchived group."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['pos.config'].create({'name': 'Archive Test Shop'})
        cls.manager = new_test_user(cls.env, 'pos_arch_mgr', groups='base.group_user,point_of_sale.group_pos_manager')
        cls.archiver = new_test_user(cls.env, 'pos_arch_ok', groups='base.group_user,point_of_sale.group_pos_manager,bn_pos_order.pos_config_archive_group')
        # see every Branch / Site, as a configured user of the shop would see it
        if 'all_nodes' in cls.env['res.users']._fields:
            (cls.manager | cls.archiver).write({'all_nodes': True})

    def test_archive_refused_without_group(self):
        with self.assertRaises(AccessError):
            self.config.with_user(self.manager).write({'active': False})

    def test_restore_refused_without_group(self):
        self.config.write({'active': False})
        with self.assertRaises(AccessError):
            self.config.with_user(self.manager).write({'active': True})

    def test_group_archives_and_restores(self):
        self.config.with_user(self.archiver).write({'active': False})
        self.assertFalse(self.config.active)
        self.config.with_user(self.archiver).write({'active': True})
        self.assertTrue(self.config.active)

    def test_unchanged_active_needs_no_group(self):
        self.config.with_user(self.manager).write({'active': True, 'name': 'Renamed Shop'})
        self.assertEqual(self.config.name, 'Renamed Shop')
