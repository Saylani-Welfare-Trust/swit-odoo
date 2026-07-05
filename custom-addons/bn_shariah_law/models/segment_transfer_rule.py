from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SegmentTransferRule(models.Model):
    _name = 'segment.transfer.rule'
    _description = 'Segment Transfer Rules'
    _rec_name = 'source_segment_id'
    _order = 'source_segment_id, destination_segment_id'

    source_segment_id = fields.Many2one(
        'account.analytic.account',
        string='Source Segment',
        required=True,
        domain="[('plan_id.name', '=', 'Segment')]"
    )
    
    # One source can have many destinations
    destination_segment_ids = fields.Many2many(
        'account.analytic.account',
        'segment_transfer_rule_dest_rel',
        'rule_id',
        'destination_id',
        string='Destination Segments',
        required=True,
        domain="[('plan_id.name', '=', 'Segment')]"
    )
    
    allowed = fields.Boolean(string='Transfer Allowed', default=True)
    max_transfer_amount = fields.Monetary(
        string='Maximum Transfer Amount',
        currency_field='currency_id',
        help='Maximum amount that can be transferred in a single transaction'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')
    
    # Approval settings
    requires_approval = fields.Boolean(string='Requires Approval', default=False)
    approval_group_id = fields.Many2one(
        'res.groups',
        string='Approval Group',
        help='User group that can approve transfers for this rule'
    )
    
    # Display field for destinations
    destination_names = fields.Char(
        string='Destinations',
        compute='_compute_destination_names',
        store=False
    )
    
    @api.depends('destination_segment_ids')
    def _compute_destination_names(self):
        for rec in self:
            rec.destination_names = ', '.join(rec.destination_segment_ids.mapped('name'))
    
    _sql_constraints = [
        ('unique_source', 'unique(source_segment_id, company_id)',
         'Only one rule per source segment is allowed!')
    ]

    @api.constrains('source_segment_id', 'destination_segment_ids')
    def _check_segments(self):
        for rec in self:
            if rec.source_segment_id in rec.destination_segment_ids:
                raise ValidationError(_('Source segment cannot be in destination list!'))

    @api.model
    def check_transfer_allowed(self, source_id, dest_id, amount=0.0):
        """Check if a transfer is allowed between two segments."""
        # Find rule for source
        rule = self.search([
            ('source_segment_id', '=', source_id),
            ('active', '=', True)
        ], limit=1)
        
        if not rule:
            source = self.env['account.analytic.account'].browse(source_id)
            raise ValidationError(_(
                "No transfer rule found for source segment '%s'.\n"
                "Please configure transfer rules in Segment Transfer Rules setup."
            ) % source.name)
        
        if not rule.allowed:
            source = self.env['account.analytic.account'].browse(source_id)
            raise ValidationError(_(
                "Transfers from '%s' are currently disabled."
            ) % source.name)
        
        # Check if destination is allowed
        if dest_id not in rule.destination_segment_ids.ids:
            source = self.env['account.analytic.account'].browse(source_id)
            dest = self.env['account.analytic.account'].browse(dest_id)
            raise ValidationError(_(
                "Transfer from '%s' to '%s' is not allowed.\n"
                "Please configure this destination in the transfer rules."
            ) % (source.name, dest.name))
        
        if rule.max_transfer_amount > 0 and amount > rule.max_transfer_amount:
            source = self.env['account.analytic.account'].browse(source_id)
            raise ValidationError(_(
                "Transfer amount %.2f exceeds the maximum allowed amount of %.2f "
                "for transfers from '%s'."
            ) % (amount, rule.max_transfer_amount, source.name))
        
        return rule

    @api.model
    def get_allowed_destinations(self, source_id):
        """Get all allowed destination segments for a source."""
        rule = self.search([
            ('source_segment_id', '=', source_id),
            ('active', '=', True)
        ], limit=1)
        
        if rule and rule.allowed:
            return rule.destination_segment_ids
        return self.env['account.analytic.account']

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.source_segment_id.name} → {rec.destination_names}"
            if rec.max_transfer_amount > 0:
                name += f" (Max: {rec.max_transfer_amount})"
            if not rec.allowed:
                name += " [Disabled]"
            result.append((rec.id, name))
        return result

    def toggle_active(self):
        """Toggle active status."""
        for rec in self:
            rec.active = not rec.active