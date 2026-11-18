# -*- coding: utf-8 -*-
"""Patient registration, prescription desk and billing counter, with the links
of the prescription to the POS (session, POS, cashier, bill)."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMedicalFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.product = env['product.product'].create({
            'name': 'Paracetamol', 'type': 'consu', 'available_in_pos': True, 'lst_price': 50})
        def cash(code):
            journal = env['account.journal'].create({'name': 'Cash %s' % code, 'code': code, 'type': 'cash'})
            return env['pos.payment.method'].create({'name': 'Cash %s' % code, 'journal_id': journal.id})
        cls.desk = env['pos.config'].create({
            'name': 'MH Desk', 'is_medical_pos': True, 'medical_pos_role': 'prescription',
            'payment_method_ids': [(6, 0, cash('MHD').ids)]})
        cls.counter = env['pos.config'].create({
            'name': 'MH Billing', 'is_medical_pos': True, 'medical_pos_role': 'billing',
            'payment_method_ids': [(6, 0, cash('MHB').ids)]})
        cls.desk_session = env['pos.session'].create({'config_id': cls.desk.id, 'user_id': env.uid})
        cls.counter_session = env['pos.session'].create({'config_id': cls.counter.id, 'user_id': env.uid})

    def _register(self, cnic='42101-1234567-1', name='Patient One'):
        return self.env['res.partner']._mh_register_patient({
            'name': name, 'mobile': '03001234567', 'cnic_no': cnic, 'date_of_birth': '1990-01-01'})

    def test_register_patient_once_per_person(self):
        patient, existing = self._register()
        self.assertFalse(existing)
        self.assertEqual(patient.state, 'register')
        self.assertIn(patient, self.env['res.partner'].search(self.env['res.partner']._mh_patient_domain()))
        self.assertIn(patient.id, self.env['mh.patient'].search([]).ids)
        again, existing = self._register(cnic='4210112345671', name='Other Name')
        self.assertTrue(existing)
        self.assertEqual(again, patient)

    def test_existing_contact_becomes_the_patient(self):
        contact = self.env['res.partner'].create({'name': 'Walk In', 'cnic_no': '42101-7654321-1'})
        patient, existing = self._register(cnic='42101-7654321-1', name='Walk In')
        self.assertTrue(existing)
        self.assertEqual(patient, contact)
        self.assertEqual(patient.state, 'register')
        self.assertTrue(patient.date_of_birth)

    def test_prescription_desk_and_billing(self):
        patient, _existing = self._register()
        data = self.desk_session.pos_approve_medical_prescription({
            'partner_id': patient.id, 'doctor_name': 'Dr. A',
            'lines': [{'product_id': self.product.id, 'qty': 2, 'price_unit': 50}]})
        prescription = self.env['medical.prescription'].browse(data['id'])
        self.assertEqual(prescription.state, 'approved')
        self.assertEqual(prescription.pos_session_id, self.desk_session)
        self.assertEqual(prescription.pos_config_id, self.desk)

        # the desk cannot bill, the counter cannot approve
        with self.assertRaises(Exception):
            self.desk_session.pos_check_medical_prescription(prescription.id, patient.id)
        with self.assertRaises(Exception):
            self.counter_session.pos_approve_medical_prescription({'partner_id': patient.id, 'lines': []})
        self.assertTrue(self.counter_session.pos_check_medical_prescription(prescription.id, patient.id))

        order = self.env['pos.order'].create({
            'session_id': self.counter_session.id, 'partner_id': patient.id,
            'medical_prescription_id': prescription.id,
            'amount_tax': 0, 'amount_total': 50, 'amount_paid': 50, 'amount_return': 0,
            'lines': [(0, 0, {'product_id': self.product.id, 'qty': 1, 'price_unit': 50,
                              'price_subtotal': 50, 'price_subtotal_incl': 50})]})
        prescription._mark_billed(order)
        self.assertEqual(prescription.state, 'billed')
        self.assertEqual(prescription.pos_order_id, order)
        self.assertEqual(prescription.pos_session_id, self.counter_session)
        self.assertEqual(prescription.pos_config_id, self.counter)
        self.assertIn('prescribed 2.0, billed 1.0', prescription.message_ids[:1].body)
        with self.assertRaises(UserError):
            self.counter_session.pos_check_medical_prescription(prescription.id, patient.id)
        with self.assertRaises(UserError):
            prescription.action_cancel()
