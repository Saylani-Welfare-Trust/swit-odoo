from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SecurityOffered(models.Model):
    _name = 'security.offered'
    _description = 'Security Offered for Microfinance'
    _order = 'name'

    name = fields.Char('Security Type', required=True)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)
    
    # Track usage
    microfinance_count = fields.Integer(
        'Used in Applications', 
        compute='_compute_microfinance_count'
    )
    
    def _compute_microfinance_count(self):
        """Count how many microfinance applications use this security type"""
        for record in self:
            record.microfinance_count = self.env['microfinance'].search_count([
                ('security_offered_id', '=', record.id)
            ])
    
    def action_view_microfinance(self):
        """Open microfinance records using this security type"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Microfinance Applications'),
            'res_model': 'microfinance',
            'view_mode': 'tree,form',
            'domain': [('security_offered_id    ', '=', self.id)],
            'context': {'create': False},
        }
    
    _sql_constraints = [
        ('unique_security_name', 
         'UNIQUE(name)',
         'Security type name must be unique!')
    ]