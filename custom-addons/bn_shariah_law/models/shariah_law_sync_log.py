from odoo import fields, models


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

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.module_name} - {record.sync_date}"
            result.append((record.id, name))
        return result