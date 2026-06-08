from odoo import models, fields

class WelfareDocument(models.Model):
    _name = 'welfare.document'
    _description = 'Welfare Document'

    welfare_id = fields.Many2one('welfare', ondelete='cascade', required=True)
    document_type = fields.Selection([
        ('application_form', 'Application Form'),
        ('frc',              'FRC'),
        ('electricity_bill', 'Electricity Bill'),
        ('gas_bill',         'Gas Bill'),
        ('family_cnic',      'Family CNIC'),
    ], required=True)
    attachment_id = fields.Many2one('ir.attachment', ondelete='cascade', required=True)
    name     = fields.Char(related='attachment_id.name', store=True)
    mimetype = fields.Char(related='attachment_id.mimetype')
    url      = fields.Char(compute='_compute_url')

    def _compute_url(self):
        for rec in self:
            rec.url = f'/web/content/{rec.attachment_id.id}?download=true' if rec.attachment_id else ''

    def action_delete(self):
        self.ensure_one()
        welfare_id = self.welfare_id.id
        self.attachment_id.unlink()
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'welfare',
            'res_id': welfare_id,
            'view_mode': 'form',
            'target': 'current',
        }