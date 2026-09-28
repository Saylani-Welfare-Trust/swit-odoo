from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class SmsTemplate(models.Model):
    _name = 'sms.template'
    _description = 'SMS Message Template'
    _rec_name = 'name'

    name = fields.Char(string='Template Name', required=True, default='Donation SMS Template')
    message = fields.Text(string='SMS Message', required=True, 
        default="""Dear {donor_name},

Thank you for your donation!

Amount: {amount} PKR
Items:
{items}

May Allah bless you!

- SWIT""")
    
    is_active = fields.Boolean(string='Active', default=True)
    
    @api.constrains('is_active')
    def _check_active(self):
        for record in self:
            if record.is_active:
                other_active = self.search([('is_active', '=', True), ('id', '!=', record.id)])
                if other_active:
                    other_active.write({'is_active': False})
    
    @api.model
    def create(self, vals):
        # Disable create - only edit allowed
        if self.search_count([]) >= 1:
            raise UserError(_('Only one template record is allowed. Please edit the existing record.'))
        return super(SmsTemplate, self).create(vals)
    
    def write(self, vals):
        # Allow edit only
        result = super(SmsTemplate, self).write(vals)
        
        # If this record becomes active, deactivate others
        if vals.get('is_active'):
            other_records = self.search([('is_active', '=', True), ('id', '!=', self.id)])
            if other_records:
                other_records.write({'is_active': False})
        
        return result
    
    def unlink(self):
        # Disable delete
        raise UserError(_('You cannot delete this record. Only editing is allowed.'))
    
    def action_send_message(self):
        """Send message button action - will be called from POS"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Send SMS',
            'res_model': 'sms.send.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
    
    def get_rendered_message(self, donor_name, amount, items):
        """Render message with dynamic values"""
        try:
            rendered = self.message.format(
                donor_name=donor_name or '',
                amount=amount or '',
                items=items or ''
            )
            return rendered
        except Exception as e:
            _logger.error(f'Message rendering error: {e}')
            return self.message