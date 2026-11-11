from odoo import fields, models


class MedicalPatient(models.Model):
    _inherit = 'mh.patient'

    prescription_count = fields.Integer('Prescriptions', compute='_compute_prescription_count')
    bill_count = fields.Integer('Bills', compute='_compute_prescription_count')

    def _compute_prescription_count(self):
        Prescription = self.env['medical.prescription']
        partners = self.partner_id
        prescriptions = dict(Prescription._read_group(
            [('partner_id', 'in', partners.ids)], ['partner_id'], ['__count']))
        bills = dict(Prescription._read_group(
            [('partner_id', 'in', partners.ids), ('pos_order_id', '!=', False)], ['partner_id'], ['__count']))
        for patient in self:
            patient.prescription_count = prescriptions.get(patient.partner_id, 0)
            patient.bill_count = bills.get(patient.partner_id, 0)

    def action_view_prescriptions(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('bn_medical_prescription.medical_prescription_action')
        action['domain'] = [('partner_id', '=', self.partner_id.id)]
        action['context'] = {'default_partner_id': self.partner_id.id}
        return action

    def action_view_bills(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('bn_medical_prescription.action_mh_bills')
        action['domain'] = [('medical_prescription_id.partner_id', '=', self.partner_id.id)]
        return action
