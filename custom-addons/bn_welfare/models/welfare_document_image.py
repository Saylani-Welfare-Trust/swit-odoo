from odoo import models, fields

class WelfareDocumentImage(models.Model):
    _name = 'welfare.document.image'
    _description = 'Welfare Document Image'

    welfare_id = fields.Many2one('welfare', string='Welfare', ondelete='cascade')
    document_type = fields.Selection([
        ('application_form', 'Application Form'),
        ('frc',              'FRC'),
        ('electricity_bill', 'Electricity Bill'),
        ('gas_bill',         'Gas Bill'),
        ('family_cnic',      'Family CNIC'),
    ], string='Document Type', required=True)
    image    = fields.Binary('Image', required=True)
    filename = fields.Char('Filename')

    def action_delete_self(self):
        self.ensure_one()
        welfare_id = self.welfare_id.id
        self.unlink()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'welfare',
            'res_id': welfare_id,
            'view_mode': 'form',
            'target': 'current',
        }