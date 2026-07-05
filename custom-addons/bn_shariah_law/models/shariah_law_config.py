from odoo import api, fields, models, _


class ShariahLawConfig(models.Model):
    _name = 'shariah.law.config'
    _description = 'Shariah Law Configuration'
    _rec_name = 'company_id'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    # Enable/Disable sync for each module
    enable_pos_sync = fields.Boolean(string='Sync POS Donations', default=True)
    enable_donations_sync = fields.Boolean(string='Sync Donations (DIK)', default=True)
    enable_dik_sync = fields.Boolean(string='Sync Donation In Kind (DIK)', default=True)
    enable_api_donation_sync = fields.Boolean(string='Sync API / Wallet Donations', default=True)
    enable_expense_sync = fields.Boolean(string='Sync Expenses', default=True)
    enable_purchase_sync = fields.Boolean(string='Sync Purchase Orders (PO)', default=True)
    enable_welfare_sync = fields.Boolean(string='Sync Welfare (Cash)', default=True)
    enable_microfinance_sync = fields.Boolean(string='Sync Microfinance (Cash)', default=True)
    enable_transfer_sync = fields.Boolean(string='Sync Transfers', default=True)
    
    # Sync schedule configuration
    sync_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('hourly', 'Hourly'),
        ('manual', 'Manual Only'),
    ], string='Sync Frequency', default='daily')
    
    last_sync_date = fields.Datetime(string='Last Sync Date')
    next_sync_date = fields.Datetime(string='Next Sync Date')
    
    # Error handling
    stop_on_error = fields.Boolean(string='Stop on Error', default=True)
    email_notification = fields.Boolean(string='Send Email Notification on Error', default=True)
    notification_email = fields.Char(string='Notification Email')
    
    # Logging
    sync_log_ids = fields.One2many('shariah.law.sync.log', 'config_id', string='Sync Logs')
    
    _sql_constraints = [
        ('unique_company', 'unique(company_id)', 'Only one configuration per company is allowed!')
    ]

    @api.model
    def get_config(self):
        """Get the configuration for the current company."""
        config = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not config:
            config = self.create({'company_id': self.env.company.id})
        return config

    def action_view_logs(self):
        """View sync logs."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shariah Law Sync Logs'),
            'res_model': 'shariah.law.sync.log',
            'view_mode': 'tree,form',
            'domain': [('config_id', '=', self.id)],
            'target': 'current',
        }