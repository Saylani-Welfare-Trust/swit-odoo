from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DonationHomeServiceLine(models.Model):
    _name = 'medical.equipment.line'
    _description = "Medical Equipment Line"


    medical_equipment_id = fields.Many2one('medical.equipment', string="Donation Home Service")
    medical_equipment_category_id = fields.Many2one('medical.equipment.category', string="Medical Equipment Category")
    product_id = fields.Many2one(related='medical_equipment_category_id.product_id', string="Product", store=True)
    currency_id = fields.Many2one('res.currency', related='medical_equipment_id.currency_id')
    
    quantity = fields.Integer('Quantity', default=1)
    base_security_deposit = fields.Monetary(
        string='Base Security Deposit', 
        related='medical_equipment_category_id.security_deposit',
        readonly=True
    )
    actual_deposit_percentage = fields.Float(
        string='Actual Deposit Percentage (%)',
        related='medical_equipment_id.actual_deposit_percentage',
        readonly=True,
        store=True
    )
    security_deposit = fields.Monetary(
        string='Security Deposit',
        compute='_compute_security_deposit',
        store=True
    )

    @api.depends('base_security_deposit', 'actual_deposit_percentage', 'quantity')
    def _compute_security_deposit(self):
        """
        Calculate security deposit based on base amount and master's actual deposit percentage.
        Formula: (base_security_deposit / 100) * actual_deposit_percentage
        """
        for line in self:
            if line.base_security_deposit and line.actual_deposit_percentage:
                calculated = (line.base_security_deposit * line.actual_deposit_percentage) / 100.0
                line.security_deposit = calculated
            else:
                line.security_deposit = 0.0

    @api.onchange('quantity', 'product_id')
    def _onchange_check_on_hand(self):
        """
        Validate that entered quantity does not exceed available stock
        in the source location (e.g., WH/Stock) for internal transfers.
        """
        if self.product_id and self.product_id.detailed_type != 'service':
            # Determine source location (use stock location by default)
            source_location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)

            if source_location:
                # Get available quantity for the product at source location
                qty_available = self.env['stock.quant']._get_available_quantity(
                    self.product_id, source_location
                )

                # Validate quantity
                if self.quantity > qty_available:
                    raise ValidationError(_(
                        "You have entered a quantity greater than the available quantity "
                        "in %s (Available: %s, Entered: %s)"
                    ) % (source_location.display_name, qty_available, self.quantity))