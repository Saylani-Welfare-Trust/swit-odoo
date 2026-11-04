from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # A donee keeps one institutional portal login for all their applications
    sadqa_portal_login = fields.Char('Sadqa e Jariya Portal Login', readonly=True, copy=False)
