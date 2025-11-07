from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'


    medical_equipment_ids = fields.One2many('medical.equipment', 'donee_id', string="Medical Equipments")