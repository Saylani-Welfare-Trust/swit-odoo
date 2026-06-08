class WelfareDocumentPreview(models.TransientModel):
    _name = 'welfare.document.preview'
    _description = 'Document Preview'

    document_id = fields.Many2one('welfare.document', required=True)
    image_data = fields.Binary(string='Image', related='document_id.attachment_id.datas')
    name = fields.Char(related='document_id.name')
    mimetype = fields.Char(related='document_id.mimetype')
    
    def action_download(self):
        return {
            'type': 'ir.actions.act_url',
            'url': self.document_id.url,
            'target': 'new',
        }
    
    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}