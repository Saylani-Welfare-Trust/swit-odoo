class WelfareDocumentPreview(models.TransientModel):
    _name = 'welfare.document.preview'
    _description = 'Document Preview'
    
    document_id = fields.Many2one('welfare.document', string='Document', required=True)
    attachment_id = fields.Many2one('ir.attachment', related='document_id.attachment_id', string='Attachment')
    image_data = fields.Binary(string='Image', related='attachment_id.datas')
    
    def action_close(self):
        """Close the preview dialog"""
        return {'type': 'ir.actions.act_window_close'}