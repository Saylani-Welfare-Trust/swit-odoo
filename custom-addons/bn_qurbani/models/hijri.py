from odoo import models, fields, api, exceptions


class Hijri(models.Model):
    _name = 'hijri'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Hijri'

    name = fields.Char('Hijri', tracking=True)
    approved = fields.Boolean('Approved', default=True, tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to enforce rule"""
        unapproved_count = self.search_count([('approved', '=', True)])
        if unapproved_count > 0:
            raise exceptions.UserError(
                "Cannot create new records. Please unchecked all existing approved records first."
            )
        return super(Hijri, self).create(vals_list)
