from odoo import models, fields, api

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
    ], required=True, string='Document Type')

    attachment_id = fields.Many2one(
        'ir.attachment', ondelete='cascade', required=True, string='Attachment'
    )
    name     = fields.Char(related='attachment_id.name', store=True, string='Filename')
    mimetype = fields.Char(related='attachment_id.mimetype', string='Type')
    url      = fields.Char(compute='_compute_url', string='Download URL')

    @api.depends('attachment_id')
    def _compute_url(self):
        for rec in self:
            if rec.attachment_id:
                rec.url = f'/web/content/{rec.attachment_id.id}?download=true'
            else:
                rec.url = ''

    def action_delete(self):
        self.ensure_one()
        welfare_id = self.welfare_id.id
        if self.attachment_id:
            self.attachment_id.unlink()
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'welfare',
            'res_id': welfare_id,
            'view_mode': 'form',
            'target': 'current',
        }