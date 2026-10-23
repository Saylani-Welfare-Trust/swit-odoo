# -*- coding: utf-8 -*-
"""Each step of the donation box flow done by the role that owns it, with
only that module's group: no Inventory, Key Management or Rider Shift rights
are needed for the side effects in the other modules."""
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .test_closed_box import BoxFlowCase


@tagged('post_install', '-at_install')
class TestRoles(BoxFlowCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def user(login, *groups):
            return cls.env['res.users'].create({'name': login, 'login': login, 'groups_id': [
                (6, 0, [cls.env.ref('base.group_user').id] + [cls.env.ref(g).id for g in groups])]})
        cls.db_user = user('role_db_user', 'bn_donation_box.donation_box_user_group')
        cls.db_manager = user('role_db_manager', 'bn_donation_box.donation_box_manager_group')
        cls.key_user = user('role_key_user', 'bn_key_management.key_management_user_group')
        cls.rider_user = user('role_rider_user', 'bn_rider_shift.rider_shift_user_group')
        cls.auditor = user('role_auditor', 'bn_donation_box.donation_box_audit_group',
                           'bn_key_management.key_management_audit_group', 'bn_rider_shift.rider_shift_audit_group')
        cls.rider.user_id = cls.rider_user

    def _request_and_install(self):
        request = self.env['donation.box.request'].with_user(self.db_user).create({
            'rider_id': self.installer.id, 'warehouse_id': self.warehouse.id,
            'donation_box_request_line_ids': [(0, 0, {
                'product_id': self.product.id, 'lot_id': self.lot.id, 'lock_no': 'L1'})]})
        with self.assertRaises(AccessError):
            request.action_approve()  # User cannot approve
        request.with_user(self.db_manager).action_approve()
        registration = request.donation_box_registration_installation_ids.with_user(self.db_user)
        registration.write({
            'shop_name': 'Shop', 'contact_person': 'Owner', 'location': 'Saddar', 'shop_plot_no': '1',
            'street': 'Main', 'landmark': 'Mosque', 'block_floor_office_no': 'G',
            'installation_category_id': self.installation_category.id, 'donor_id': self.donor.id})
        registration.action_install()
        registration = registration.with_user(self.db_manager)
        registration.write({'city_id': self.city.id, 'zone_id': self.zone.id,
                            'sub_zone_id': self.sub_zone.id, 'key_bunch_id': self.bunch.id})
        registration.action_approved()
        return request, registration

    def test_each_role_does_its_own_step(self):
        request, registration = self._request_and_install()
        self.assertEqual(request.picking_id.state, 'done')
        self.assertEqual(registration.status, 'available')
        key = registration.sudo().key_ids
        self.assertEqual(key.state, 'available')

        issuance = self.env['key.issuance'].with_user(self.key_user).create({
            'rider_id': self.rider.id, 'key_id': key.id, 'issue_date': fields.Date.today()})
        issuance.action_issue()
        collection = issuance.rider_collection_id
        self.assertTrue(collection)

        line = self.env['rider.schedule.line'].with_user(self.rider_user).create({
            'rider_collection_id': collection.id, 'rider_id': self.rider.id, 'date': issuance.issue_date,
            'donation_box_registration_installation_id': registration.id, 'amount': 250,
            'remarks': 'shop closed', 'box_status': 'return'})
        line.action_generate_complain()
        line.mark_as_submit()
        self.assertEqual((collection.sudo().state, collection.sudo().amount), ('donation_submit', 250))
        with self.assertRaises(ValidationError):
            line.mark_as_submit()  # already submitted
        with self.assertRaises(UserError):
            collection.with_user(self.rider_user).write({'amount': 1})  # Edit Amount group only

        complaint = registration.sudo().complain_center_ids
        self.assertEqual(complaint.status, 'draft')
        complaint.with_user(self.db_user).action_process()
        with self.assertRaises(AccessError):
            complaint.with_user(self.db_user).action_resolve()
        issuance.sudo()._bn_write({'state': 'donation_receive'})
        issuance.with_user(self.key_user).action_return()
        complaint.with_user(self.db_manager).action_resolve()
        complaint.with_user(self.db_manager).action_return()
        self.assertEqual(registration.status, 'close')
        self.assertEqual(complaint.return_picking_id.state, 'done')

    def test_rider_reports_only_own_collection(self):
        request, registration = self._request_and_install()
        issuance = self.env['key.issuance'].with_user(self.key_user).create({
            'rider_id': self.rider.id, 'key_id': registration.sudo().key_ids.id, 'issue_date': fields.Date.today()})
        issuance.action_issue()
        other = self.env['rider.schedule.line'].with_user(self.rider_user).create({
            'rider_collection_id': issuance.rider_collection_id.id, 'rider_id': self.installer.id,
            'date': issuance.issue_date, 'donation_box_registration_installation_id': registration.id, 'amount': 1})
        with self.assertRaises(AccessError):
            other.mark_as_submit()

    def test_request_line_return_by_manager(self):
        request = self.env['donation.box.request'].create({
            'rider_id': self.installer.id, 'warehouse_id': self.warehouse.id,
            'donation_box_request_line_ids': [(0, 0, {
                'product_id': self.product.id, 'lot_id': self.lot.id, 'lock_no': 'L1'})]})
        request.action_approve()
        line = request.donation_box_request_line_ids
        with self.assertRaises(AccessError):
            line.with_user(self.db_user).action_draft_line()
        line.with_user(self.db_manager).action_draft_line()
        self.assertTrue(line.is_returned)

    def test_audit_reads_everything_writes_nothing(self):
        self._request_and_install()
        for model in ('donation.box.request', 'donation.box.registration.installation', 'donation.box.complain.center',
                      'key', 'key.issuance', 'key.bunch', 'rider.collection', 'foreign.currency'):
            Model = self.env[model].with_user(self.auditor)
            Model.search_read([], ['display_name'], limit=5)
            self.assertFalse(Model.check_access_rights('write', raise_exception=False), model)
