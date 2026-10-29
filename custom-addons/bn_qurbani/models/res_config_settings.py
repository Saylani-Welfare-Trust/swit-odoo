from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    
    enable_qurbani = fields.Boolean('Enable Qurbani', config_parameter='enable_qurbani')