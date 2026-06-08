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
    
    # Computed fields for better display
    file_size = fields.Char(string='Size', compute='_compute_file_size')
    is_image = fields.Boolean(string='Is Image', compute='_compute_is_image')

    def _compute_url(self):
        for rec in self:
            rec.url = f'/web/content/{rec.attachment_id.id}?download=true' if rec.attachment_id else ''

    def _compute_file_size(self):
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

    def _compute_is_image(self):
        for rec in self:
            rec.is_image = rec.mimetype and rec.mimetype.startswith('image/')

    def action_view_document(self):
        """Open image in a modal dialog"""
        self.ensure_one()
        if self.is_image:
            # Use Odoo's built-in image viewer
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/image/{self.attachment_id.id}?unique={self.attachment_id.write_date}',
                'target': 'new',
            }
        else:
            # Download non-image files
            return {
                'type': 'ir.actions.act_url',
                'url': self.url,
                'target': 'new',
            }

    def action_delete(self):
        self.ensure_one()
        welfare_id = self.welfare_id.id
        attachment = self.attachment_id
        self.unlink()
        if attachment:
            attachment.unlink()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'welfare',
            'res_id': welfare_id,
            'view_mode': 'form',
            'target': 'current',
        }