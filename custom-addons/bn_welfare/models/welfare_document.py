from odoo import models, fields

class WelfareDocument(models.Model):
    _name = 'welfare.document'
    _description = 'Welfare Document'
    _order = 'id desc'

    welfare_id = fields.Many2one('welfare', ondelete='cascade', required=True)
    document_type = fields.Selection([
        ('application_form', 'Application Form'),
        ('frc', 'FRC'),
        ('electricity_bill', 'Electricity Bill'),
        ('gas_bill', 'Gas Bill'),
        ('family_cnic', 'Family CNIC'),
    ], required=True)
    attachment_id = fields.Many2one('ir.attachment', ondelete='cascade', required=True)
    name = fields.Char(related='attachment_id.name', store=True)
    mimetype = fields.Char(related='attachment_id.mimetype')
    url = fields.Char(compute='_compute_url')
    
    # NEW FIELDS FOR BETTER DISPLAY
    image_thumbnail = fields.Binary(string='Thumbnail', compute='_compute_image_thumbnail')
    file_size = fields.Char(string='Size', compute='_compute_file_size')
    icon_class = fields.Char(string='Icon', compute='_compute_icon_class')

    def _compute_url(self):
        for rec in self:
            rec.url = f'/web/content/{rec.attachment_id.id}?download=true' if rec.attachment_id else ''

    def _compute_image_thumbnail(self):
        """Generate thumbnail for images"""
        for rec in self:
            if rec.attachment_id and rec.mimetype and rec.mimetype.startswith('image/'):
                # For images, return the actual image data
                rec.image_thumbnail = rec.attachment_id.datas
            else:
                rec.image_thumbnail = False

    def _compute_file_size(self):
        """Calculate human-readable file size"""
        for rec in self:
            if rec.attachment_id and rec.attachment_id.file_size:
                size = rec.attachment_id.file_size
                if size < 1024:
                    rec.file_size = f"{size} B"
                elif size < 1024 * 1024:
                    rec.file_size = f"{size/1024:.1f} KB"
                else:
                    rec.file_size = f"{size/(1024*1024):.1f} MB"
            else:
                rec.file_size = False

    def _compute_icon_class(self):
        """Return appropriate icon class based on mimetype"""
        for rec in self:
            if rec.mimetype:
                if rec.mimetype.startswith('image/'):
                    rec.icon_class = 'fa-file-image-o'
                elif rec.mimetype == 'application/pdf':
                    rec.icon_class = 'fa-file-pdf-o'
                else:
                    rec.icon_class = 'fa-file-o'
            else:
                rec.icon_class = 'fa-file-o'

    def action_view_document(self):
        """View document in a modal"""
        self.ensure_one()
        if self.mimetype and self.mimetype.startswith('image/'):
            return {
                'type': 'ir.actions.act_window',
                'name': 'View Document',
                'res_model': 'welfare.document.preview',
                'view_mode': 'form',
                'target': 'new',
                'res_id': self.id,
                'context': {
                    'default_document_id': self.id,
                }
            }
        else:
            # For non-images, just download
            return {
                'type': 'ir.actions.act_url',
                'url': self.url,
                'target': 'new',
            }

    def action_delete(self):
        self.ensure_one()
        welfare_id = self.welfare_id.id
        # Store the attachment ID before unlinking
        attachment = self.attachment_id
        # First delete the document record
        self.unlink()
        # Then delete the attachment
        if attachment:
            attachment.unlink()
        # Return to form view with success notification
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'welfare',
            'res_id': welfare_id,
            'view_mode': 'form',
            'target': 'current',
        }