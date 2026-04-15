from odoo import fields, models, api
from odoo.exceptions import ValidationError


action_type_selection = [
    ('issue', 'Issue'),
    ('return', 'Return'),
]


class ManualKeyIssuance(models.TransientModel):
    _name = 'manual.key.issuance'
    _description = 'Manual Key Issuance'


    action_type = fields.Selection(selection=action_type_selection, string="Type")

    rider_id = fields.Many2one('hr.employee', string="Rider")
    
    lot_id = fields.Many2one('stock.lot', string="Box No.", domain="[('id', 'in', available_lot_ids)]")
    available_lot_ids = fields.Many2many('stock.lot', string="Available Lots", compute="_compute_available_lot_ids")

    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        required=True
    )

    @api.depends('action_type')
    def _compute_available_lot_ids(self):
        for rec in self:
            lot_ids = []

            if rec.action_type == 'issue':
                # Only available keys
                keys = self.env['key'].search([
                    ('state', '=', 'available'),
                    ('lot_id', '!=', False)
                ])
                lot_ids = keys.mapped('lot_id').ids

            elif rec.action_type == 'return':
                # Keys where:
                # payment received + submitted in POS + DN prepared
                key_issuances = self.env['key.issuance'].search([
                    ('state', 'in', ['donation_receive'])
                ])
                lot_ids = key_issuances.mapped('key_id.lot_id').ids

            rec.available_lot_ids = [(6, 0, lot_ids)]

    def _get_key(self):
        """Search for key by lot_id"""
        if not self.lot_id:
            raise ValidationError('Please select a Box No.')
        
        key = self.env['key'].search([('lot_id', '=', self.lot_id.id)], limit=1)
        
        if not key:
            raise ValidationError(f'Key with Box No. "{self.lot_id.name}" not found')
        
        return key

    def action_issue(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        
        key = self._get_key()
        
        if key.state != 'available':
            raise ValidationError(f'Key "{key.name}" is not available for issuance')
        
        key_issuance_obj = self.env['key.issuance'].create({
            'rider_id': self.rider_id.id,
            'key_id': key.id
        })

        key_issuance_obj.action_issue()

    def action_return(self):
        if not self.rider_id:
            raise ValidationError('Please Select a Rider')
        
        key = self._get_key()
        
        key_issuance = self.env['key.issuance'].search([
            ('key_id', '=', key.id), 
            ('state', '=', 'issued')
        ], limit=1)
        
        if key_issuance:
            raise ValidationError(f'Please move key "{key.name}" to Donation Received state first.')

        key_issuance = self.env['key.issuance'].search([
            ('key_id', '=', key.id),
            ('state', 'in', ['donation_receive'])
        ], limit=1)
        
        if key_issuance:
            key_issuance.action_return()
        else:
            raise ValidationError(f'No issuance record found for key "{key.name}" in Donation Received state.')
