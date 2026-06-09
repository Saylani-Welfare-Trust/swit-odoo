from odoo import models, fields, api
from odoo.exceptions import UserError

class WelfareDocument(models.Model):
    _name = 'welfare.document'
    _description = 'Welfare Document'
    _rec_name = 'name'
    _order = 'create_date desc'
    
    welfare_id = fields.Many2one('welfare', string='Welfare Request', required=True, ondelete='cascade')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', required=True, ondelete='cascade')
    
    # Related fields from attachment
    name = fields.Char(string='Document Name', related='attachment_id.name', store=True)
    mimetype = fields.Char(string='Mime Type', related='attachment_id.mimetype')
    file_size = fields.Integer(string='File Size', related='attachment_id.file_size')
    create_date = fields.Datetime(string='Upload Date', related='attachment_id.create_date')
    
    def action_view_document(self):
        """View document directly in browser"""
        self.ensure_one()
        
        if not self.attachment_id:
            raise UserError("No document attached.")
        
        # Simply open the document in a new tab
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=false',
            'target': 'new',
        }
    
    def action_delete(self):
        """Delete the document and its attachment"""
        self.ensure_one()
        
        # Store the welfare_id before unlinking
        welfare_id = self.welfare_id.id
        
        if not welfare_id:
            raise UserError("Cannot delete: Document is not linked to any welfare record.")
        
        # Store attachment for later deletion
        attachment = self.attachment_id
        
        # Delete the document record
        self.unlink()
        
        # Delete the attachment if it exists
        if attachment:
            attachment.unlink()
        
        # Return to the welfare form view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'welfare',
            'res_id': welfare_id,
            'view_mode': 'form',
            'target': 'current',
        }