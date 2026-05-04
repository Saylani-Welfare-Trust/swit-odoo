
from odoo import models, fields, api
from odoo.exceptions import UserError  # <-- Ye import karna hai
import logging
class ResPartner(models.Model):
    _inherit = 'res.partner'


    whatsapp = fields.Char(string="WhatsApp")