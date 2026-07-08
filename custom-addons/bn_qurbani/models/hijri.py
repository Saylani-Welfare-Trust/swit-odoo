from odoo import models, fields, api, exceptions


class Hijri(models.Model):
    _name = 'hijri'
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = 'Hijri'

    name = fields.Char('Hijri', tracking=True)
    approved = fields.Boolean('Approved', default=True, tracking=True)
    
    can_create_new = fields.Boolean(string='Can Create New', compute='_compute_can_create_new')
    
    @api.depends()
    def _compute_can_create_new(self):
        """Compute if user can create new records"""
        for record in self:
            unapproved_count = self.search_count([('approved', '=', False)])
            record.can_create_new = unapproved_count == 0
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to enforce rule"""
        unapproved_count = self.search_count([('approved', '=', False)])
        if unapproved_count > 0:
            raise exceptions.UserError(
                "Cannot create new records. Please approve all existing unapproved records first."
            )
        return super(Hijri, self).create(vals_list)
