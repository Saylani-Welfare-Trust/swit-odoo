from odoo import models, fields


class MedicalEquipmentReference(models.Model):
    _name = 'medical.equipment.reference'
    _description = 'Medical Equipment Reference'

    name = fields.Char('Name', required=True)
    contact_id = fields.Many2one('res.partner', string='Contact', help='Select contact from partner list.')
