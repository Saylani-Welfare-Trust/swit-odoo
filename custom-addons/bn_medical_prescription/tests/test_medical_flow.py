# -*- coding: utf-8 -*-
"""One Medical & Health counter: paid till with a doctor, draft prescription filled and
approved on stock by the doctor's side, then billed at the counter."""
from datetime import date

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class TestMedicalFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Product = env['product.product']
        services = env['product.category'].create({'name': 'MH Services'})
        medicines = env['product.category'].create({'name': 'MH Medicines'})
        pos_medical = env['pos.category'].create({'name': 'MH POS', 'mh_medical': True, 'mh_prescription': True})
        # sold at the counter, but not offered in the prescription lines
        pos_counter_only = env['pos.category'].create({'name': 'MH Counter Only', 'mh_medical': True})
        pos_medicines = env['pos.category'].create({'name': 'MH POS Medicines', 'parent_id': pos_medical.id})
        cls.consultation = Product.create({
            'name': 'OPD Consultation', 'detailed_type': 'service', 'available_in_pos': True, 'lst_price': 200,
            'categ_id': services.id})
        cls.other_service = Product.create({
            'name': 'Eye Test', 'detailed_type': 'service', 'available_in_pos': True, 'lst_price': 300,
            'categ_id': services.id})
        cls.medicine = Product.create({
            'name': 'Paracetamol', 'detailed_type': 'product', 'available_in_pos': True, 'lst_price': 50,
            'categ_id': medicines.id, 'pos_categ_ids': [(6, 0, pos_medicines.ids)]})
        cls.counter_only = Product.create({
            'name': 'Counter Only Item', 'detailed_type': 'consu', 'available_in_pos': True,
            'categ_id': services.id, 'pos_categ_ids': [(6, 0, pos_counter_only.ids)]})
        cls.non_medical = Product.create({
            'name': 'Donation Item', 'detailed_type': 'consu', 'available_in_pos': True, 'categ_id': services.id})
        journal = env['account.journal'].create({'name': 'Cash MH', 'code': 'MHC', 'type': 'cash'})
        method = env['pos.payment.method'].create({'name': 'Cash MH', 'journal_id': journal.id})
        plan = env['account.analytic.plan'].create({'name': 'MH Branches'})
        branch = env['account.analytic.account'].create({'name': 'MH Branch', 'plan_id': plan.id})
        cls.counter = env['pos.config'].create({
            'name': 'MH Counter', 'is_medical_pos': True, 'payment_method_ids': [(6, 0, method.ids)],
            'analytic_account_id': branch.id})
        cls.session = env['pos.session'].create({'config_id': cls.counter.id, 'user_id': env.uid})
        cls.location = cls.counter.picking_type_id.default_location_src_id

        # a doctor only has the groups Doctor and Menu: no POS, branch or Allowed Categories
        groups = [env.ref('base.group_user').id, env.ref('bn_medical_pos.group_medical_doctor').id,
                  env.ref('bn_medical_pos.group_medical_menu').id]
        cls.doctor_user = env['res.users'].create({
            'name': 'Doctor User', 'login': 'mh_doctor_user', 'groups_id': [(6, 0, groups)], 'all_nodes': True})
        cls.other_user = env['res.users'].create({
            'name': 'Other User', 'login': 'mh_other_user', 'groups_id': [(6, 0, groups)], 'all_nodes': True})
        cls.doctor = env['medical.doctor'].create({
            'name': 'Dr. A', 'product_ids': [(6, 0, cls.consultation.ids)], 'user_ids': [(6, 0, cls.doctor_user.ids)]})
        cls.other_doctor = env['medical.doctor'].create({
            'name': 'Dr. B', 'product_ids': [(6, 0, cls.other_service.ids)], 'user_ids': [(6, 0, cls.other_user.ids)]})
        cls.patient, _existing = env['res.partner']._mh_register_patient({
            'name': 'Patient One', 'mobile': '03001234567', 'cnic_no': '42101-1234567-1', 'date_of_birth': '1990-01-01'})

    def _order(self, product, doctor=False, prescription=False, amount=200):
        now = str(fields.Datetime.now())
        uid = '00001-%03d-0001' % (self.env['pos.order'].search_count([]) + 1)
        result = self.env['pos.order'].create_from_ui([{'id': uid, 'to_invoice': False, 'data': {
            'name': 'Order %s' % uid, 'uid': uid, 'amount_paid': amount, 'amount_total': amount, 'amount_tax': 0,
            'amount_return': 0, 'pos_session_id': self.session.id, 'pricelist_id': self.counter.pricelist_id.id,
            'partner_id': self.patient.id, 'user_id': self.env.uid, 'sequence_number': 1, 'creation_date': now,
            'date_order': now, 'fiscal_position_id': False, 'to_invoice': False, 'server_id': False,
            'medical_doctor_id': doctor and doctor.id, 'medical_prescription_id': prescription and prescription.id,
            'lines': [[0, 0, {'product_id': product.id, 'qty': 1, 'price_unit': amount, 'discount': 0,
                              'price_subtotal': amount, 'price_subtotal_incl': amount, 'tax_ids': [[6, False, []]],
                              'full_product_name': product.name, 'pack_lot_ids': []}]],
            'statement_ids': [[0, 0, {'payment_method_id': self.counter.payment_method_ids[0].id,
                                      'amount': amount, 'name': now}]],
        }}])
        return self.env['pos.order'].browse(result[0]['id'])

    def _till(self):
        order = self._order(self.consultation, doctor=self.doctor)
        return order, self.env['medical.prescription'].search([('intake_order_id', '=', order.id)])

    def _stock(self, qty):
        self.env['stock.quant']._update_available_quantity(self.medicine, self.location, qty)

    def test_doctors_follow_the_selected_products(self):
        doctors = self.session.pos_get_medical_doctors(self.consultation.ids)
        self.assertEqual([doctor['id'] for doctor in doctors], self.doctor.ids)
        self.assertFalse(self.session.pos_get_medical_doctors((self.consultation | self.other_service).ids))

    def test_paid_till_makes_an_empty_draft(self):
        order, prescription = self._till()
        self.assertEqual(len(prescription), 1)
        self.assertEqual(prescription.state, 'draft')
        self.assertEqual(prescription.doctor_id, self.doctor)
        self.assertEqual(prescription.category_product_ids, self.consultation)
        self.assertFalse(prescription.line_ids)
        self.assertEqual(prescription.intake_order_id, order)
        self.assertFalse(prescription.pos_order_id, "the till is not the bill of the prescription")
        self.assertEqual(self.session.pos_get_till_prescription(order.id), prescription.name)
        self.assertFalse(self.session.pos_get_medical_prescriptions(self.patient.id, ''))

    def test_approval_needs_stock(self):
        _order, prescription = self._till()
        prescription = prescription.with_user(self.doctor_user)
        self.assertEqual(prescription.category_name, 'OPD Consultation', "shown outside the user's product categories")
        with self.assertRaises(UserError):
            prescription.action_approve()  # no product yet
        prescription.write({'line_ids': [(0, 0, {'product_id': self.medicine.id, 'qty': 2, 'price_unit': 1})]})
        self.assertEqual(prescription.line_ids.price_unit, 50, "a user adds products at their sales price")
        with self.assertRaises(UserError):
            prescription.action_approve()  # on hand 0
        self.assertEqual(prescription.state, 'draft')
        self._stock(-3)
        with self.assertRaises(UserError):
            prescription.action_approve()  # negative on hand
        self._stock(5)
        prescription.action_approve()
        self.assertEqual(prescription.state, 'approved')
        self.assertEqual(prescription.approved_by_id, self.doctor_user)
        self.assertEqual(len(self.session.pos_get_medical_prescriptions(self.patient.id, '')), 1)
        with self.assertRaises(UserError):
            prescription.line_ids.qty = 9  # approved: locked

    def test_prescriptions_follow_the_doctor(self):
        _order, prescription = self._till()
        Prescription = self.env['medical.prescription']
        self.assertIn(prescription, Prescription.with_user(self.doctor_user).search([]))
        self.assertNotIn(prescription, Prescription.with_user(self.other_user).search([]))
        with self.assertRaises(AccessError):
            prescription.with_user(self.other_user).action_approve()
        with self.assertRaises(AccessError):
            prescription.with_user(self.doctor_user).write({'state': 'approved'})
        with self.assertRaises(AccessError):
            prescription.with_user(self.doctor_user).write({'doctor_id': self.other_doctor.id})

    def test_doctor_with_only_doctor_and_menu_groups(self):
        _order, prescription = self._till()
        self.assertTrue(prescription.pos_analytic_account_id, "made at a branch the doctor isn't scoped on")
        as_doctor = prescription.with_user(self.doctor_user)
        self.assertEqual(self.env['medical.prescription'].with_user(self.doctor_user).search([]), prescription)
        self.assertTrue(as_doctor.has_till)
        Product = self.env['product.product'].with_user(self.doctor_user)
        self.assertIn(self.medicine, Product.search([]), "products of a sub-category of a Medical & Health category")
        self.assertNotIn(self.non_medical, Product.search([]))
        for model in ('pos.order', 'pos.session'):
            self.assertFalse(self.env[model].with_user(self.doctor_user).check_access_rights('read', False))
        with self.assertRaises(AccessError):
            self.env['medical.prescription'].with_user(self.doctor_user).create({'partner_id': self.patient.id})
        as_doctor.write({'line_ids': [(0, 0, {'product_id': self.medicine.id, 'qty': 1})]})
        self._stock(1)
        as_doctor.action_approve()
        self.assertEqual(prescription.state, 'approved')

    def test_doctor_stays_limited_with_settings_rights(self):
        _order, mine = self._till()
        others = self.env['medical.prescription'].create({'partner_id': self.patient.id, 'doctor_id': self.other_doctor.id})
        no_doctor = self.env['medical.prescription'].create({'partner_id': self.patient.id})
        everything = mine | others | no_doctor
        Prescription = self.env['medical.prescription']
        settings = self.env.ref('base.group_system')
        self.doctor_user.groups_id = [(4, settings.id)]
        self.assertEqual(Prescription.with_user(self.doctor_user).search([('id', 'in', everything.ids)]), mine)
        # Settings with a Medical group but not Doctor, and Medical Administrators, keep seeing everything
        admin = self.env['res.users'].create({
            'name': 'Settings User', 'login': 'mh_settings_user', 'all_nodes': True,
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, settings.id,
                                  self.env.ref('bn_medical_pos.group_medical_user').id])]})
        self.assertEqual(Prescription.with_user(admin).search([('id', 'in', everything.ids)]), everything)
        self.doctor_user.groups_id = [(4, self.env.ref('bn_medical_pos.group_medical_manager').id)]
        self.assertEqual(Prescription.with_user(self.doctor_user).search([('id', 'in', everything.ids)]), everything)

    def test_product_line_follows_the_pos_categories(self):
        _order, prescription = self._till()
        domain = safe_eval(self.env['medical.prescription.line']._fields['product_id'].domain)
        offered = self.env['product.product'].search(domain)
        self.assertIn(self.medicine, offered, "in a sub-category of a Prescription category")
        self.assertNotIn(self.non_medical, offered)
        self.assertNotIn(self.counter_only, offered, "Medical & Health without Prescription: counter only")
        # a doctor has no POS rights: the dropdown still has to work for them
        self.assertEqual(self.env['product.product'].with_user(self.doctor_user).search(domain) & self.medicine, self.medicine)
        for product in (self.non_medical, self.counter_only):
            with self.assertRaises(ValidationError):
                prescription.write({'line_ids': [(0, 0, {'product_id': product.id, 'qty': 1})]})
        self.assertFalse(prescription.line_ids)

    def test_number_restarts_every_day(self):
        _order, prescription = self._till()
        today = fields.Date.context_today(prescription).strftime('%d%m%Y')
        self.assertRegex(prescription.name, r'^RX/%s/\d{4}$' % today)
        Sequence = self.env['ir.sequence']
        later = date(2099, 1, 1)
        self.assertEqual(Sequence.next_by_code('medical.prescription', sequence_date=later), 'RX/01012099/0001')
        self.assertEqual(Sequence.next_by_code('medical.prescription', sequence_date=later), 'RX/01012099/0002')
        self.assertEqual(Sequence.next_by_code('medical.prescription', sequence_date=date(2099, 1, 2)), 'RX/02012099/0001')

    def test_on_hand_shown_and_prices_hidden(self):
        _order, prescription = self._till()
        self._stock(7)
        prescription.write({'line_ids': [(0, 0, {'product_id': self.medicine.id, 'qty': 1})]})
        line = prescription.with_user(self.doctor_user).line_ids
        self.assertTrue(line.is_storable)
        self.assertEqual(line.qty_on_hand, 7)
        view = self.env.ref('bn_medical_prescription.medical_prescription_view_form')
        doctor_arch = self.env['medical.prescription'].with_user(self.doctor_user).get_view(view.id)['arch']
        self.assertIn('qty_on_hand', doctor_arch)
        for price in ('price_unit', 'price_subtotal', 'amount_total'):
            self.assertNotIn('name="%s"' % price, doctor_arch)
        manager = self.env['res.users'].create({
            'name': 'MH Admin', 'login': 'mh_admin_view',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('bn_medical_pos.group_medical_manager').id])]})
        self.assertIn('name="price_unit"', self.env['medical.prescription'].with_user(manager).get_view(view.id)['arch'])

    def test_doctor_chooses_the_location(self):
        _order, prescription = self._till()
        self.assertEqual(prescription.location_id, self.location, "the counter's stock location by default")
        shelf = self.env['stock.location'].create({'name': 'MH Shelf', 'usage': 'internal', 'location_id': self.location.location_id.id})
        self.assertIn(shelf, self.env['stock.location'].with_user(self.doctor_user).search([('usage', '=', 'internal')]))
        as_doctor = prescription.with_user(self.doctor_user)
        as_doctor.write({'location_id': shelf.id, 'line_ids': [(0, 0, {'product_id': self.medicine.id, 'qty': 1})]})
        self._stock(5)  # at the counter's location, not on the shelf
        self.assertEqual(as_doctor.line_ids.qty_on_hand, 0)
        with self.assertRaises(UserError):
            as_doctor.action_approve()
        self.env['stock.quant']._update_available_quantity(self.medicine, shelf, 2)
        as_doctor.invalidate_recordset()
        self.assertEqual(as_doctor.line_ids.qty_on_hand, 2)
        as_doctor.action_approve()
        self.assertEqual(prescription.state, 'approved')

    def test_bill_of_the_approved_prescription(self):
        _order, prescription = self._till()
        prescription.write({'line_ids': [(0, 0, {'product_id': self.medicine.id, 'qty': 1, 'price_unit': 50})]})
        self._stock(1)
        prescription.action_approve()
        self.assertTrue(self.session.pos_check_medical_prescription(prescription.id, self.patient.id))
        bill = self._order(self.medicine, prescription=prescription, amount=50)
        self.assertEqual(prescription.state, 'billed')
        self.assertEqual(prescription.pos_order_id, bill)
        self.assertFalse(bill.medical_doctor_id, "a bill doesn't make another prescription")
        self.assertEqual(self.env['medical.prescription'].search_count([('intake_order_id', '=', bill.id)]), 0)
        with self.assertRaises(UserError):
            self.session.pos_check_medical_prescription(prescription.id, self.patient.id)
