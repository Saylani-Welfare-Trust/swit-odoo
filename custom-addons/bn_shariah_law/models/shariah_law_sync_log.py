from odoo import api, fields, models


class ShariahLawSyncLog(models.Model):
    _name = 'shariah.law.sync.log'
    _description = 'Shariah Law Sync Log'
    _order = 'sync_date desc'

    config_id = fields.Many2one('shariah.law.config', string='Configuration')
    sync_date = fields.Datetime(string='Sync Date', default=fields.Datetime.now)
    module_name = fields.Char(string='Module')
    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ], string='Status')
    message = fields.Text(string='Message')
    records_synced = fields.Integer(string='Records Synced')
    error_details = fields.Text(string='Error Details')
    duration = fields.Float(string='Duration (seconds)')
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('module_name', 'sync_date')
    def _compute_display_name(self):
        # (Odoo 17 no longer calls name_get)
        for record in self:
            record.display_name = f"{record.module_name or ''} - {record.sync_date or ''}"
