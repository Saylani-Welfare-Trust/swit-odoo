from odoo import fields, models, api

class ShariahLawBlocker(models.Model):
    _name = 'shariah.law.blocker'
    _description = 'Shariah Law Blocker'
    _rec_name = 'company_id'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    # Enable/Disable for each module
    enable_pos = fields.Boolean(string='POS', default=True)
    enable_donations = fields.Boolean(string='Wallet', default=True)
    enable_dik = fields.Boolean(string='Donation In Kind', default=True)
    enable_expense = fields.Boolean(string='Expenses', default=True)
    enable_purchase = fields.Boolean(string='Purchase Orders', default=True)
    enable_welfare = fields.Boolean(string='Welfare (Cash)', default=True)
    enable_microfinance = fields.Boolean(string='Microfinance (Cash)', default=True)
    enable_transfer = fields.Boolean(string='Transfers', default=True)

    _sql_constraints = [
        ('unique_company', 'unique(company_id)', 'Only one blocker record per company is allowed!')
    ]

    @api.model
    def get_blocker_config(self):
        """Get the blocker configuration for the current company."""
        config = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.create({'company_id': self.env.company.id})
        return config

    def is_module_blocked(self, module_key):
        """Check if a specific module is blocked."""
        config = self.get_blocker_config()
        field_map = {
            'pos': 'enable_pos',
            'donations': 'enable_donations',
            'dik': 'enable_dik',
            'expense': 'enable_expense',
            'purchase': 'enable_purchase',
            'welfare': 'enable_welfare',
            'microfinance': 'enable_microfinance',
            'transfer': 'enable_transfer',
        }
        
        field_name = field_map.get(module_key)
        if field_name:
            return not getattr(config, field_name, True)
        return False