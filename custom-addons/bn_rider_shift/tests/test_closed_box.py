# -*- coding: utf-8 -*-
"""A donation box taken out of service (registration Closed) and the same box
number reused in a new request. Covers bn_donation_box, bn_key_management and
bn_rider_shift together, which is why it lives in the top module of the chain."""
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


class BoxFlowCase(TransactionCase):
    """Shared fixture: one serial-tracked box in stock, analytic city / zone /
    sub zone, a key bunch, an installer, a rider and a registered DB donor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        ref = env.ref
        option = {name: env['location.option'].search([('name', '=', name)], limit=1)
                  or env['location.option'].create({'name': name}) for name in ('City', 'Zone')}
        plan = env['account.analytic.plan'].create({'name': 'Geo'})
        Account = env['account.analytic.account']
        cls.city = Account.create({'name': 'Karachi', 'plan_id': plan.id, 'location_option_id': option['City'].id})
        cls.zone = Account.create({'name': 'Zone South', 'plan_id': plan.id,
                                   'location_option_id': option['Zone'].id, 'parent_id': cls.city.id})
        cls.sub_zone = env['sub.zone'].create({'name': 'Saddar', 'analytic_account_id': cls.zone.id})
        cls.bunch = env['key.bunch'].create({'name': 'Bunch A', 'city_id': cls.city.id,
                                             'zone_id': cls.zone.id, 'sub_zone_id': cls.sub_zone.id})
        cls.installer = env['hr.employee'].create({
            'name': 'Installer I', 'cnic_no': '42101-9876501-1',
            'category_ids': [(6, 0, ref('bn_donation_box.installer_hr_employee_category').ids)]})
        cls.rider = env['hr.employee'].create({
            'name': 'Rider R', 'cnic_no': '42101-9876502-1',
            'category_ids': [(6, 0, ref('bn_donation_box.donation_box_rider_hr_employee_category').ids)]})
        cls.product = env['product.template'].create({
            'name': 'Steel Box', 'type': 'product', 'tracking': 'serial', 'is_donation_box': True,
        }).product_variant_id
        cls.warehouse = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
        cls.lot = env['stock.lot'].create({'name': 'BOX-T1', 'product_id': cls.product.id, 'company_id': env.company.id})
        env['stock.quant']._update_available_quantity(cls.product, cls.warehouse.lot_stock_id, 1, lot_id=cls.lot)
        cls.donor = env['res.partner'].create({
            'name': 'Shop Owner', 'mobile': '3019876543',
            'category_id': [(6, 0, [ref('bn_profile_management.donor_partner_category').id,
                                    ref('bn_profile_management.individual_partner_category').id,
                                    ref('bn_profile_management.donation_box_donor_partner_category').id])]})
        cls.donor.action_register()
        cls.installation_category = env['installation.category'].create({'name': 'Shop'})
        cls.manager = env['res.users'].create({
            'name': 'Box Manager', 'login': 'box_manager_test',
            'groups_id': [(6, 0, [ref('base.group_user').id, ref('bn_donation_box.donation_box_manager_group').id])]})

    # -- helpers ---------------------------------------------------------
    def _install(self, lock_no):
        request = self.env['donation.box.request'].create({
            'rider_id': self.installer.id, 'warehouse_id': self.warehouse.id,
            'donation_box_request_line_ids': [(0, 0, {
                'product_id': self.product.id, 'lot_id': self.lot.id, 'lock_no': lock_no})]})
        request.action_approve()
        registration = request.donation_box_registration_installation_ids
        registration.write({
            'shop_name': 'Shop', 'contact_person': 'Owner', 'location': 'Saddar', 'shop_plot_no': '1',
            'street': 'Main', 'landmark': 'Mosque', 'block_floor_office_no': 'G',
            'installation_category_id': self.installation_category.id, 'donor_id': self.donor.id})
        registration.action_install()
        registration.write({'city_id': self.city.id, 'zone_id': self.zone.id,
                            'sub_zone_id': self.sub_zone.id, 'key_bunch_id': self.bunch.id})
        registration.action_approved()
        return registration

    def _complaint(self, registration, box_status='return', **vals):
        return self.env['donation.box.complain.center'].create(dict({
            'donation_box_registration_installation_id': registration.id, 'lot_id': self.lot.id,
            'rider_id': self.rider.id, 'box_status': box_status, 'remarks': 'test'}, **vals))

    def _take_out_of_service(self, registration):
        complaint = self._complaint(registration)
        complaint.action_process()
        complaint.action_resolve()
        complaint.action_return()
        return complaint



@tagged('post_install', '-at_install')
class TestClosedBox(BoxFlowCase):

    def test_closed_registration_is_final(self):
        registration = self._install('L1')
        key = registration.key_ids
        self._take_out_of_service(registration)
        self.assertEqual(registration.status, 'close')
        self.assertEqual(registration.box_status, 'removed')
        self.assertEqual(key.state, 'closed')
        self.assertFalse(self.lot.lot_consume)

        with self.assertRaises(ValidationError):
            self._complaint(registration, 'broken')
        with self.assertRaises(UserError):
            registration.with_user(self.manager).action_change_request()
        with self.assertRaises(UserError):
            registration.with_user(self.manager).write({'contact_person': 'Someone else'})
        with self.assertRaises(UserError):
            registration.with_user(self.manager).write({'key_bunch_id': False})

    def test_pending_box_return_blocks_new_complaint(self):
        registration = self._install('L1')
        complaint = self._complaint(registration)
        complaint.action_process()
        complaint.action_resolve()
        with self.assertRaises(ValidationError):
            self._complaint(registration, 'missing', complain_officer_id=self.rider.id)
        complaint.action_return()
        self.assertEqual(registration.status, 'close')

    def test_recovered_missing_box_can_be_returned(self):
        registration = self._install('L1')
        complaint = self._complaint(registration, 'missing', complain_officer_id=self.rider.id)
        complaint.action_process()
        complaint.write({'complain_officer_remark': 'found', 'box_recovered': True})
        complaint.action_resolve()
        self.assertEqual(registration.status, 'close')
        complaint.action_return()
        self.assertEqual(complaint.return_picking_id.state, 'done')
        self.assertFalse(self.lot.lot_consume)

    def test_reused_box_number_uses_the_registration_in_service(self):
        old = self._install('L1')
        old_key = old.key_ids
        self._take_out_of_service(old)
        new = self._install('L2')
        new_key = new.key_ids
        self.assertNotEqual(old, new)

        Registration = self.env['donation.box.registration.installation']
        self.assertEqual(Registration._bn_find_by_lot(self.lot), new)

        wizard = self.env['manual.key.issuance'].create({
            'action_type': 'issue', 'rider_id': self.rider.id, 'lot_id': self.lot.id})
        self.assertEqual(wizard.key_id, new_key)
        self.assertEqual(old_key.state, 'closed')

        complaint = self.env['donation.box.complain.center'].create({
            'lot_id': self.lot.id, 'rider_id': self.rider.id, 'box_status': 'broken', 'remarks': 'x'})
        self.assertEqual(complaint.donation_box_registration_installation_id, new)

        foreign = self.env['foreign.currency'].create({
            'rider_id': self.rider.id, 'lot_id': self.lot.id, 'amount': 10,
            'exchanged_amount': 2800, 'state': 'converted'})
        foreign.action_create_pos_record()
        self.assertEqual(foreign.rider_collection_id.donation_box_registration_installation_id, new)

    def test_reused_box_rider_marks_pending(self):
        old = self._install('L1')
        self._take_out_of_service(old)
        new = self._install('L2')
        issuance = self.env['key.issuance'].create({
            'rider_id': self.rider.id, 'key_id': new.key_ids.id, 'issue_date': fields.Date.today()})
        issuance.action_issue()
        line = self.env['rider.schedule.line'].create({
            'rider_collection_id': issuance.rider_collection_id.id, 'rider_id': self.rider.id,
            'date': issuance.issue_date, 'donation_box_registration_installation_id': new.id,
            'remarks': 'shop shut'})
        line.mark_as_pending()
        self.assertEqual(issuance.state, 'pending')
