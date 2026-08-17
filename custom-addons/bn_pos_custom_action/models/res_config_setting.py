from odoo import models, fields

class ResConfigSettiongsInhert(models.TransientModel):
    _inherit = "res.config.settings"

    
    counter = fields.Integer(related="pos_config_id.counter",readonly=False)
    sequence = fields.Integer(related="pos_config_id.sequence",readonly=True)