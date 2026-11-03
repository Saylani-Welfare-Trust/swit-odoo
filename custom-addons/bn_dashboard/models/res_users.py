from odoo import models

class ResUsers(models.Model):
    _inherit = 'res.users'

    def get_allowed_analytic_ids(self):
        """Map the user's allowed stock locations/warehouses to analytic account IDs."""
        self.ensure_one()
        if self.has_group('base.group_system'):
            return []
        
        allowed_ids = []
        if 'allowed_location_ids' in self._fields and self.allowed_location_ids:
            model_name = self.allowed_location_ids._name
            if model_name == 'stock.location':
                if 'analytic_account_id' in self.env['stock.location']._fields:
                    allowed_ids = self.allowed_location_ids.mapped('analytic_account_id').ids
            elif model_name == 'account.analytic.account':
                allowed_ids = self.allowed_location_ids.ids
        
        # Fallback to allowed warehouses if no locations matched
        if not allowed_ids and 'allowed_warehouse_ids' in self._fields and self.allowed_warehouse_ids:
            if 'analytic_account_id' in self.env['stock.warehouse']._fields:
                allowed_ids = self.allowed_warehouse_ids.mapped('analytic_account_id').ids
            else:
                locs = self.env['stock.location'].search([
                    ('warehouse_id', 'in', self.allowed_warehouse_ids.ids), 
                    ('analytic_account_id', '!=', False)
                ])
                allowed_ids = locs.mapped('analytic_account_id').ids
                
        return list(set(allowed_ids))