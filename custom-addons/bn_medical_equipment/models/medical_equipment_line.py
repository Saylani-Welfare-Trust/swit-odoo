from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DonationHomeServiceLine(models.Model):
    _name = 'medical.equipment.line'
    _description = "Medical Equipment Line"


    medical_equipment_id = fields.Many2one('medical.equipment', string="Donation Home Service")
    medical_equipment_category_id = fields.Many2one('medical.equipment.category', string="Medical Equipment Category")
    product_id = fields.Many2one('product.product', string="Product",related='medical_equipment_category_id.product_id', store=True )
    currency_id = fields.Many2one('res.currency', related='medical_equipment_id.currency_id')
    lot_ids = fields.Many2many('stock.lot', string="Product No./Lot")

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
    reference_line_ids = fields.One2many(
    'medical.equipment.line',          # change to 'medical.equipment.reference.line' if different
    compute='_compute_reference_lines',
    string='Reference Items',
    readonly=True
)

    @api.depends('medical_equipment_reference_id')
    def _compute_reference_lines(self):
        """Auto‑detect and fetch lines from the selected reference."""
        for record in self:
            lines = self.env['medical.equipment.line'].browse()
            ref = record.medical_equipment_reference_id
            
            if ref:
                # 1) Try common one2many field names on the reference
                for candidate in ['line_ids', 'reference_line_ids', 'medical_equipment_line_ids']:
                    if hasattr(ref, candidate) and ref[candidate]:
                        lines = ref[candidate]
                        break
                
                # 2) If not found, search for lines linked via 'reference_id' on the line model
                if not lines and 'reference_id' in self.env['medical.equipment.line']._fields:
                    lines = self.env['medical.equipment.line'].search([
                        ('reference_id', '=', ref.id)
                    ])
                
                # 3) If still nothing, try a different line model (if exists)
                if not lines and 'medical.equipment.reference.line' in self.env.registry:
                    lines = self.env['medical.equipment.reference.line'].search([
                        ('reference_id', '=', ref.id)
                    ])
            
            record.reference_line_ids = lines
    
    # allowed_lot_ids = fields.Many2many(
    #     'stock.lot',
    #     string="Allowed Lots",
    #     compute="_compute_allowed_lot_ids",
    # )
    @api.constrains('lot_ids', 'product_id')
    def _check_lot_ids(self):
        for record in self:
            # Only validate if tracking is required
            if record.product_id.tracking != 'none':
                if not record.lot_ids:
                    raise ValidationError(_("Product No./Lot is required."))
    
    @api.constrains('lot_ids', 'quantity')
    def _check_lot_quantity(self):
        for rec in self:
            if rec.quantity and len(rec.lot_ids) > rec.quantity:
                raise ValidationError(
                    f"You can only select {rec.quantity} lot(s) based on the quantity."
                )

    # @api.depends('product_id',)
    # def _compute_allowed_lot_ids(self):
    #     for line in self:
    #         if not line.product_id:
    #             line.allowed_lot_ids = [(5, 0, 0)]  # empty domain
    #             continue

    #         lots = self.env['stock.lot'].search([
    #             ('product_id', '=', line.product_id.id),
    #         ])

    #         lot_ids = lots.filtered(lambda l: not l.lot_consume)
    #         line.allowed_lot_ids = lot_ids

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