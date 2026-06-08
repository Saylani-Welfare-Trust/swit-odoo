from odoo import models, api, fields
from odoo.exceptions import UserError as Warning

class WelfareDocument(models.Model):
    _name = 'welfare.document'
    _description = 'Welfare Document'
    _order = 'sequence, id'
    
    welfare_id = fields.Many2one('welfare', string='Welfare', required=True, ondelete='cascade')
    doc_type = fields.Selection([
        ('application_form', 'Application Form'),
        ('frc', 'FRC'),
        ('electricity_bill', 'Electricity Bill'),
        ('gas_bill', 'Gas Bill'),
        ('family_cnic', 'Family CNIC'),
    ], string='Document Type', required=True)
    
    name = fields.Char('Document Name', required=True)
    file_data = fields.Binary('File', attachment=True, required=True)
    sequence = fields.Integer('Sequence', default=10)
    portal_url = fields.Char('Portal URL')
    description = fields.Char('Description')
    
    # For backward compatibility with single fields
    is_primary = fields.Boolean('Primary Document', default=False)