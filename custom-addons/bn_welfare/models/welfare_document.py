from odoo import models, fields, api
from odoo.exceptions import UserError

class WelfareDocumentImage(models.Model):
    _name = 'welfare.document.image'
    _description = 'Welfare Document Image'

    welfare_id = fields.Many2one('welfare', string='Welfare', ondelete='cascade')
    document_type = fields.Selection([
        ('application_form', 'Application Form'),
        ('frc', 'FRC'),
        ('electricity_bill', 'Electricity Bill'),
        ('gas_bill', 'Gas Bill'),
        ('family_cnic', 'Family CNIC'),
    ], string='Document Type', required=True)
    image_data = fields.Binary('Image', attachment=True)
    image_filename = fields.Char('Filename')
    source_url = fields.Char('Source URL')
    
    # This field is OPTIONAL - remove if causing issues
    display_image = fields.Html(
        string='Preview',
        compute='_compute_display_image',
        sanitize=False,
        store=False
    )
    
    @api.depends('image_data', 'source_url', 'image_filename', 'document_type')
    def _compute_display_image(self):
        for rec in self:
            label = dict(rec._fields['document_type'].selection).get(rec.document_type, 'Document')
            
            if rec.image_data and rec.id and isinstance(rec.id, int):
                rec.display_image = (
                    f'<a href="/web/image/welfare.document.image/{rec.id}/image_data" '
                    f'target="_blank" '
                    f'class="btn btn-sm btn-primary" '
                    f'style="text-decoration:none;">'
                    f'📄 View {label}'
                    f'</a>'
                )
            elif rec.source_url:
                rec.display_image = (
                    f'<a href="{rec.source_url}" '
                    f'target="_blank" '
                    f'class="btn btn-sm btn-info" '
                    f'style="text-decoration:none;">'
                    f'🔗 View {label}'
                    f'</a>'
                )
            else:
                rec.display_image = '<span class="text-muted">❌ No Image</span>'