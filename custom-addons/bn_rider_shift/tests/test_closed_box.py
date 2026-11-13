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
        self.assertEqual(Registration._find_by_lot(self.lot), new)

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


@tagged('post_install', '-at_install')
class TestBunchOut(BoxFlowCase):
    """A bunch goes out with a rider as a whole: nothing about one of its
    boxes changes until every key of the bunch is back."""

    def _issue(self, key):
        issuance = self.env['key.issuance'].create({
            'rider_id': self.rider.id, 'key_id': key.id, 'issue_date': fields.Date.today()})
        issuance.action_issue()
        return issuance

    def test_change_request_waits_for_the_whole_bunch(self):
        registration = self._install('L1')
        # a second box of the same bunch, its key out with the rider
        other_lot = self.env['stock.lot'].create({'name': 'BOX-OTHER', 'product_id': self.product.id})
        self.env['stock.quant']._update_available_quantity(
            self.product, self.warehouse.lot_stock_id, 1, lot_id=other_lot)
        self.lot, saved_lot = other_lot, self.lot
        other = self._install('L2')
        self.lot = saved_lot
        self.assertEqual(other.key_ids.key_bunch_id, registration.key_ids.key_bunch_id)
        issuance = self._issue(other.key_ids)

        with self.assertRaisesRegex(ValidationError, 'bunch'):
            registration.action_change_request()
        complaint = self._complaint(registration)
        complaint.action_process()
        with self.assertRaises(ValidationError):
            complaint.action_resolve()   # its bunch is still out

        issuance._workflow_write({'state': 'donation_receive'})
        issuance.action_return()
        registration.action_change_request()
        self.assertEqual(registration.status, 'change_request')


@tagged('post_install', '-at_install')
class TestCorrectClosedBoxKeys(BoxFlowCase):
    """Boxes Closed by earlier versions while their key stayed Issued in its
    bunch: the "Correct Keys of Closed Boxes" server action."""

    def _second_box(self, lot_name, lock_no):
        lot = self.env['stock.lot'].create({'name': lot_name, 'product_id': self.product.id})
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 1, lot_id=lot)
        self.lot, saved = lot, self.lot
        registration = self._install(lock_no)
        self.lot = saved
        return registration

    def _issue(self, key):
        issuance = self.env['key.issuance'].create({
            'rider_id': self.rider.id, 'key_id': key.id, 'issue_date': fields.Date.today()})
        issuance.action_issue()
        return issuance

    def _close_like_before(self, registration):
        # what earlier versions left: the box Closed, its key untouched
        registration._workflow_write({'status': 'close', 'box_status': 'removed'})

    def test_correction(self):
        plain = self._install('L1')                       # key out, nothing collected
        with_cash = self._second_box('BOX-CASH', 'L2')    # key out, cash submitted, not paid at the POS
        healthy = self._second_box('BOX-OK', 'L3')        # box still in service
        plain_issuance = self._issue(plain.key_ids)
        cash_issuance = self._issue(with_cash.key_ids)
        cash_issuance.rider_collection_id.write({'state': 'donation_submit', 'amount': 500})
        for registration in (plain, with_cash):
            self._close_like_before(registration)
        self.assertEqual(plain.key_ids.state, 'issued')
        self.assertEqual(plain.key_ids.key_bunch_id, self.bunch)

        action = self.env['donation.box.registration.installation']._correct_closed_box_keys(
            self.env['donation.box.registration.installation'])
        self.assertEqual(action['params']['type'], 'warning')   # one issuance left open

        for registration in (plain, with_cash):
            self.assertEqual(registration.key_ids.state, 'closed')
            self.assertFalse(registration.key_ids.key_bunch_id, 'out of the bunch: no more bulk issuance')
        self.assertEqual(plain_issuance.state, 'returned')
        self.assertEqual(cash_issuance.state, 'issued', 'money still to settle at the POS')
        self.assertEqual(healthy.key_ids.state, 'available')
        self.assertEqual(healthy.key_ids.key_bunch_id, self.bunch)

        # the POS settles it later: the key stays closed when it comes back
        cash_issuance._workflow_write({'state': 'donation_receive'})
        cash_issuance.action_return()
        self.assertEqual(cash_issuance.state, 'returned')
        self.assertEqual(with_cash.key_ids.state, 'closed')

        # a bulk issuance of the bunch now only takes the box in service
        self.env['bulk.key.issuance'].create({
            'rider_id': self.rider.id, 'date': fields.Date.today(), 'key_bunch_ids': [(6, 0, self.bunch.ids)],
        }).action_issue()
        issued = self.env['key.issuance'].search([('state', '=', 'issued'), ('key_id.key_bunch_id', '=', self.bunch.id)])
        self.assertEqual(issued.key_id, healthy.key_ids)

        # run again: nothing left to correct
        again = self.env['donation.box.registration.installation']._correct_closed_box_keys()
        self.assertIn('Nothing to correct', again['params']['message'])

    def test_closing_a_box_now_returns_its_open_issuance(self):
        registration = self._install('L1')
        issuance = self._issue(registration.key_ids)
        registration._take_box_out_of_service()
        registration._key_close()
        self.assertEqual(issuance.state, 'returned')
        self.assertEqual(registration.key_ids.state, 'closed')
        self.assertFalse(registration.key_ids.key_bunch_id)

    def test_only_administrators(self):
        user = self.env['res.users'].create({
            'name': 'Key User', 'login': 'key_user_fix',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('bn_key_management.key_management_user_group').id])]})
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.env['donation.box.registration.installation'].with_user(user)._correct_closed_box_keys()


@tagged('post_install', '-at_install')
class TestOneInService(BoxFlowCase):
    """Only one registration in service and one open key per box number; the
    lock number of the request reaches the registration and its key."""

    def test_one_registration_in_service(self):
        registration = self._install('L1')
        Registration = self.env['donation.box.registration.installation']
        with self.assertRaises(ValidationError):
            Registration.create({'shop_name': 'Second', 'lot_id': self.lot.id})
        self._take_out_of_service(registration)
        again = self._install('L2')                     # the box number is reused
        self.assertEqual(again.status, 'available')
        self.assertEqual(Registration.search_count([('lot_id', '=', self.lot.id), ('status', '!=', 'close')]), 1)
        self.assertEqual(registration.key_ids.state, 'closed')
        self.assertEqual(again.key_ids.state, 'available')

    def test_one_open_key(self):
        registration = self._install('L1')
        with self.assertRaises(ValidationError):
            self.env['key'].create({'name': 'Spare', 'lot_id': self.lot.id})
        spare = self.env['key'].create({'name': 'Old', 'lot_id': self.lot.id, 'state': 'closed'})
        self.assertEqual(spare.state, 'closed')
        self.assertEqual(registration.key_ids.lock_no, 'L1')

    def test_populate_lock_no_reaches_the_key(self):
        registration = self._install('L1')
        key = registration.key_ids
        registration._workflow_write({'lock_no': False})
        key.write({'lock_no': False})
        Registration = self.env['donation.box.registration.installation']
        Registration.populate_lock_no(registration)
        self.assertEqual(registration.lock_no, 'L1')
        self.assertEqual(key.lock_no, 'L1')

    def test_bulk_issue_refuses_a_key_not_returned(self):
        registration = self._install('L1')
        issuance = self.env['key.issuance'].create({
            'rider_id': self.rider.id, 'key_id': registration.key_ids.id, 'issue_date': fields.Date.today()})
        issuance.action_issue()
        issuance.action_donation_receive()
        with self.assertRaisesRegex(ValidationError, 'still out'):
            self.env['bulk.key.issuance'].create({
                'rider_id': self.rider.id, 'date': fields.Date.today(), 'key_bunch_ids': [(6, 0, self.bunch.ids)],
            }).action_issue()

    def test_not_available_while_its_bunch_is_out(self):
        first = self._install('L1')
        issuance = self.env['key.issuance'].create({
            'rider_id': self.rider.id, 'key_id': first.key_ids.id, 'issue_date': fields.Date.today()})
        issuance.action_issue()
        # a second box approved into the bunch that is out with the rider
        lot = self.env['stock.lot'].create({'name': 'BOX-T2', 'product_id': self.product.id})
        self.env['stock.quant']._update_available_quantity(self.product, self.warehouse.lot_stock_id, 1, lot_id=lot)
        self.lot, saved = lot, self.lot
        with self.assertRaisesRegex(ValidationError, 'out with a rider'):
            self._install('L2')
        self.lot = saved
        # a key left "Issued" without its issuance record also blocks it
        issuance._workflow_write({'state': 'returned'})
        self.assertEqual(first.key_ids.state, 'issued')
        with self.assertRaisesRegex(ValidationError, 'out with a rider'):
            first.key_ids._make_available(self.bunch)


@tagged('post_install', '-at_install')
class TestVisibility(BoxFlowCase):
    """Registrations: installers see their own (user level), the city staff their
    City; key bunches: the City of the bunch matches the user's City."""

    def _user(self, login, groups, account=None, employee=None):
        user = self.env['res.users'].create({
            'name': login, 'login': login,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id] + [self.env.ref(g).id for g in groups])]})
        employee = employee or self.env['hr.employee'].create({'name': login, 'cnic_no': '42101-55%05d-1' % user.id})
        employee.write({'user_id': user.id, 'analytic_account_id': (account or self.zone).id})
        return user

    def test_installer_sees_own_registrations(self):
        registration = self._install('L1')
        Registration = self.env['donation.box.registration.installation']
        installer = self._user('inst_vis', ['bn_donation_box.donation_box_user_group'], employee=self.installer)
        colleague = self._user('colleague_vis', ['bn_donation_box.donation_box_user_group'])
        key_user = self._user('key_vis', ['bn_key_management.key_management_user_group'])
        self.assertEqual(Registration.with_user(installer).search([('id', '=', registration.id)]), registration)
        self.assertFalse(Registration.with_user(colleague).search([('id', '=', registration.id)]),
                         'same city but not the installer: hidden')
        self.assertEqual(Registration.with_user(key_user).search([('id', '=', registration.id)]), registration,
                         'Key Management works on the boxes of its City')
        other_city = self.env['account.analytic.account'].create({
            'name': 'Lahore', 'plan_id': self.city.plan_id.id, 'location_option_id': self.city.location_option_id.id})
        far_key_user = self._user('far_key_vis', ['bn_key_management.key_management_user_group'], account=other_city)
        self.assertFalse(Registration.with_user(far_key_user).search([('id', '=', registration.id)]))
        manager = self._user('mgr_vis', ['bn_donation_box.donation_box_manager_group'], account=other_city)
        self.assertEqual(Registration.with_user(manager).search([('id', '=', registration.id)]), registration)

    def test_bunch_city_level(self):
        Bunch = self.env['key.bunch']
        branch = self.env['account.analytic.account'].create({
            'name': 'Saddar Branch', 'plan_id': self.city.plan_id.id, 'parent_id': self.zone.id})
        same_city = self._user('bunch_vis', ['bn_key_management.key_management_user_group'], account=branch)
        other_city = self.env['account.analytic.account'].create({
            'name': 'Multan', 'plan_id': self.city.plan_id.id, 'location_option_id': self.city.location_option_id.id})
        far = self._user('bunch_far', ['bn_key_management.key_management_user_group'], account=other_city)
        self.assertIn(self.bunch, Bunch.with_user(same_city).search([]), 'a Branch user sees the bunches of its City')
        self.assertNotIn(self.bunch, Bunch.with_user(far).search([]))
