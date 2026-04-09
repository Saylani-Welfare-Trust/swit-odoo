from odoo import models, fields, api


class QurbaniSchedule(models.Model):
    _name = 'qurbani.schedule'
    _description = 'Qurbani Schedule'

    day_id = fields.Many2one(
        'qurbani.day',
        string="Day",
        required=True
    )

    start_time = fields.Float(
        string="Start Time",
    )

    end_time = fields.Float(
        string="End Time",
    )

    livestock_product_id = fields.Many2one(
        'product.product',
        string="Livestock Product",
        domain="[('type', '=', 'product'), ('is_livestock', '=', True)]",
    )

    service_product_id = fields.Many2one(
        'product.product',
        string="Service Product",
        domain="[('type', '=', 'service'), ('is_livestock', '=', True)]",
    )

    location_id = fields.Many2one(
        'stock.location',
        string="Location",
    )

    qty_available = fields.Float(
        related='livestock_product_id.qty_available',
        string="On Hand Quantity",
        readonly=True
    )

    total_hissa = fields.Integer(
        string="Total Hissa",
        store=True,
        compute="_compute_total_hissa"
    )

    pos_hissa = fields.Integer(
        string="POS Hissa",
        default=0
    )

    option = fields.Selection(
        [
            ('yes', 'Yes'),
            ('no', 'No')
        ],   
        default="yes", 
        string="option"
    )
    
    @api.depends('livestock_product_id', 'qty_available')
    def _compute_total_hissa(self):
        for record in self:
            hissa_per_unit = 0

            product_name = record.livestock_product_id.name.lower()

            if 'cow' in product_name:
                hissa_per_unit = 7
            elif 'goat' in product_name:
                hissa_per_unit = 1

            record.total_hissa = hissa_per_unit * record.qty_available