from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


state_selection = [
    ('pending', 'Pending'),
    ('delivered', 'Delivered'),
    ('not_applicable', 'Not Applicable'),
    ('approved', 'Approved'),
]


class QurbaniGoatDistribution(models.Model):
    _name = 'qurbani.goat.distribution'
    _description = "Qurbani Goat Distribution"


    hijri_id = fields.Many2one('hijri', string="Hijri")
    day_id = fields.Many2one('qurbani.day', string="Day")
    inventory_product_id = fields.Many2one('product.product', string="Inventory Product")
    distribution_location_id = fields.Many2one('stock.location', string="Distribution Location")
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location")

    start_time = fields.Float('Start Time')
    end_time = fields.Float('End Time')
    slaughter_start_time = fields.Float('Start Time')
    slaughter_end_time = fields.Float('End Time')

    name = fields.Char('Name', default="New")

    product_id = fields.Many2one('product.product', string="Product")

    qurbani_order_no = fields.Char('QO No.')
    qurbani_order_line_no = fields.Char('QOL No.')
    hissa_name = fields.Char('Hissa Name')
    
    state = fields.Selection(selection=state_selection, string="State", default='Pending')

    remarks = fields.Text('Remarks')


    @api.model
    def create(self, vals):
        if vals.get('name', _('New') == _('New')):
            vals['name'] = self.env['ir.sequence'].next_by_code('qurbani_goat_distribution') or ('New')

        return super(QurbaniGoatDistribution, self).create(vals)
    
    def action_approved(self):
        for rec in self:
            if not rec.remarks:
                raise ValidationError('Please enter the remarks first for No meet approval.')
            
            rec.state = 'approved'
    
    def action_print_report(self):
        records_to_print = self.env[self._name]

        for rec in self:

            # STOP invalid records
            if rec.state not in ['pending', 'approved']:
                raise ValidationError(
                    f'A record {rec.name} has already been delivered / delivery is not applicable.'
                )

            # PROCESS RECORD
            if 'yes' in rec.product_id.name.lower():
                rec.state = 'delivered'

            # ADD FOR PRINTING
            records_to_print |= rec

        # PRINT ONLY PROCESSED/VALID RECORDS
        return self.env.ref(
            'bn_qurbani.qurbani_goat_distribution_report'
        ).report_action(records_to_print)