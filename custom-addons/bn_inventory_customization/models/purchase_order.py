from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    # Why a receipt of this order was closed without a backorder, or cancelled
    receipt_reason_ids = fields.One2many('purchase.receipt.reason', 'order_id', string='Receipt Reasons')

    # What a confirmed order is waiting for. It is a field of its own, not extra
    # values of `state`: Odoo's receipt and billing logic only knows a confirmed
    # order as 'purchase' or 'done'.
    receipt_bill_state = fields.Selection([
        ('to_receive', 'Waiting Receipt'),
        ('to_bill', 'Received - To Bill'),
        ('billed', 'Billed'),
    ], string="Receipt / Bill Status", compute='_compute_receipt_bill_state', store=True)

    @api.depends('state', 'receipt_status', 'invoice_status')
    def _compute_receipt_bill_state(self):
        """The bill is created from the receipt (stock.picking.action_create_bill),
        so an order needs one as soon as something has been received and is not
        billed yet. After a partial receipt has been billed, the order waits for
        the rest of its receipt again."""
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.receipt_bill_state = False
            elif order.invoice_status == 'to invoice' and order.receipt_status != 'pending':
                order.receipt_bill_state = 'to_bill'
            elif order.invoice_status == 'invoiced' and order.receipt_status in (False, 'full'):
                order.receipt_bill_state = 'billed'
            else:
                order.receipt_bill_state = 'to_receive'


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # store the original base unit price (before multiplier)
    x_base_price = fields.Float(string="Base Unit Price")
    # store chosen to_kg multiplier
    to_kg_multiplier = fields.Float(string="To KG Multiplier", default=1.0)

    @api.onchange('product_id')
    def onchange_product_id(self):
        """Extend Odoo's product onchange for livestock: the price entered is per kg,
           a unit is estimated at the heaviest weight band of the product
           (Livestock Variants), price_unit = per-kg price x that weight.
        """
        super().onchange_product_id()

        for line in self:
            if not line.product_id:
                line.x_base_price = 0.0
                line.to_kg_multiplier = 1.0
                continue

            if not line.product_id.check_stock:
                line.x_base_price = line.price_unit or 0.0
                line.to_kg_multiplier = 1.0
                continue

            # --- 1) Determine reliable base price ---
            base_price = 0.0
            partner = line.order_id.partner_id if line.order_id else False

            if partner:
                sellers = line.product_id.seller_ids.filtered(lambda s: s.display_name == partner)
                if sellers:
                    seller_prices = [s.price for s in sellers if s.price is not None]
                    if seller_prices:
                        base_price = min(seller_prices)

            if not base_price:
                if line.price_unit and line.price_unit not in (0.0, 1.0):
                    base_price = line.price_unit

            if not base_price:
                base_price = line.product_id.standard_price or line.product_id.list_price or 0.0

            line.x_base_price = float(base_price or 0.0)

            # --- 2) Heaviest configured weight band of this purchase product ---
            max_to_kg = self.env['livestock.variant.line']._max_weight(line.product_id)
            line.to_kg_multiplier = float(max_to_kg or 1.0)

            # --- 3) Apply final unit price ---
            line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier)

    @api.onchange('product_qty')
    def _onchange_product_qty_reapply_multiplier(self):
        """When qty changes, reapply price_unit from saved base to prevent price drift.
           This avoids price_unit being reset to 1 or multiplied again incorrectly.
        """
        for line in self:
            if not line.product_id or not line.product_id.check_stock:
                continue
            # If we have a saved base price, reapply it
            if line.x_base_price:
                line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier)

    @api.onchange('price_unit')
    def _onchange_price_unit_store_base(self):
        """If user manually edits price_unit, update x_base_price accordingly so we keep
           consistent behavior (base = price_without_multiplier).
        """
        for line in self:
            if not line.product_id or not line.product_id.check_stock:
                continue
            if line.to_kg_multiplier and line.to_kg_multiplier != 1.0:
                # If user changes price_unit manually, store underlying base
                try:
                    base = float(line.price_unit) / float(line.to_kg_multiplier)
                except Exception:
                    base = float(line.price_unit)
                line.x_base_price = base
            else:
                line.x_base_price = float(line.price_unit or 0.0)

    def _compute_amount(self):
        """Ensure amounts are correct server-side (in case lines are created/updated by code).
           Recompute based on x_base_price and to_kg_multiplier when applicable, then call super to compute taxes & totals.
        """
        # Before calling super, ensure price_unit is consistent server-side
        for line in self:
            if line.product_id and line.product_id.check_stock:
                if line.x_base_price:
                    # apply base*multiplier as price_unit
                    line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier or 1.0)
                else:
                    # if no saved base, try to derive base from current price_unit
                    try:
                        base = float(line.price_unit) / float(line.to_kg_multiplier or 1.0)
                    except Exception:
                        base = float(line.price_unit or 0.0)
                    line.x_base_price = base
                    line.price_unit = float(line.x_base_price) * float(line.to_kg_multiplier or 1.0)

        # Now let Odoo compute subtotal/taxes normally
        super(PurchaseOrderLine, self)._compute_amount()

    def _livestock_moves(self):
        """The received moves of the weighed units of this (livestock) line."""
        self.ensure_one()
        return self.move_ids.filtered(lambda m: m.state == 'done' and m.livestock_amount
                                      and not m.origin_returned_move_id)

    def _get_po_line_moves(self):
        """The weighed units are received as the products of their weight bands,
        not as the purchase product: they are this line's receipt all the same."""
        moves = super()._get_po_line_moves()
        if self.product_id.check_stock:
            moves |= self.move_ids.filtered(lambda m: m.livestock_weight)
        return moves

    def _prepare_account_move_line(self, move=False):
        """A livestock line is billed at what its units weighed: the average
        weighed amount per received unit of this line (not of the whole receipt)."""
        res = super(PurchaseOrderLine, self)._prepare_account_move_line(move)
        if self.product_id.check_stock:
            moves = self._livestock_moves()
            units = sum(moves.mapped('product_uom_qty'))
            if units:
                res['price_unit'] = sum(moves.mapped('livestock_amount')) / units
        return res
