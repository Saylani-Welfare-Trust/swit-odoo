from odoo import models, api, fields
from odoo.exceptions import UserError
import io, base64
import uuid
from odoo import models, fields
import base64
import qrcode
from io import BytesIO

class PosOrder(models.Model):
    _inherit = 'pos.order'

    slaughter_qr = fields.Binary("Slaughter QR", store=False)

    def _compute_slaughter_qr(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for order in self:
            # Assuming one slaughter record per order for simplicity
            slaughter = self.env['live_stock_slaughter.live_stock_slaughter'].search([('pos_name', '=', order.name)],
                                                                                     limit=1)
            if slaughter:
                record_url = f"{base_url}/web#id={slaughter.id}&model=live_stock_slaughter.live_stock_slaughter&view_type=form"
                qr = qrcode.make(record_url)
                buffer = BytesIO()
                qr.save(buffer, format="PNG")
                qr_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                order.slaughter_qr = qr_base64
            else:
                order.slaughter_qr = False

    # def export_for_printing(self):
    #     result = super().export_for_printing()
    #     result['slaughter_qr'] = self.slaughter_qr or False
    #     print("QR CODE => %s", self.slaughter_qr)
    #     return result

    @api.model
    def create(self, vals):
        order = super(PosOrder, self).create(vals)

        print('hellooo')

        # Decide applicable lines:
        # - If order has more than 1 line -> all lines are applicable (do it for any product in line)
        # - Otherwise (single line) -> only if product has check_stock or has_check_stock
        if len(order.lines) > 1:
            applicable_lines = order.lines
        else:
            applicable_lines = []
            for line in order.lines:
                product = line.product_id
                check_flag = bool(
                    getattr(product, 'check_stock', False) or
                    getattr(product, 'has_check_stock', False)
                )
                if check_flag:
                    applicable_lines.append(line)

        # If no applicable lines, simply return the order (do nothing)
        if not applicable_lines:
            return order

        # Manually search for the 'Slaughter Stock' location (only when needed)
        cutting_location = self.env['stock.location'].search([('name', '=', 'Slaughter Stock')], limit=1)
        if not cutting_location:
            raise UserError("Cutting location not found. Please create a stock location named 'Slaughter Stock'.")

        # Get an internal picking type (used for moves)
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'internal')], limit=1)
        if not picking_type:
            raise UserError("Internal picking type not found. Please configure stock picking types.")

        for line in applicable_lines:
            product = line.product_id
            quantity = line.qty
            price = line.price_subtotal_incl
            donee_id = order.partner_id.id if order.partner_id else False
            name = order.name
            donee_name = order.partner_id.name if order.partner_id else False
            print('doneeeee', donee_name)

            # Create a record in live_stock_slaughter model
            a = self.env['live_stock_slaughter.live_stock_slaughter'].create({
                'product_new': product.id,
                'product_code': product.default_code,
                'quantity': quantity,
                'donee': donee_id,
                'price': price,
                'pos_name': name,
            })

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
            if not base_url:
                print("web.base.url not set — internal links will be incomplete.")

            # Build internal backend URL (requires login to open)
            token = uuid.uuid4().hex
            a.sudo().write({'access_token': token})

            internal_url = '{base}/live_slaughter/{id}/{token}'.format(
                base=base_url.rstrip('/'), id=a.id, token=token)

            # Generate server-side PNG QR if qrcode lib is available
            try:
                import qrcode  # pip install qrcode pillow on server
                img = qrcode.make(internal_url)
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
                a.sudo().write({'qr_code': qr_b64, 'qr_mime': 'image/png'})
            except Exception as e:
                print("QR generation failed (qrcode lib missing?): %s", e)
                # fallback: client-side rendering in POS using a.ext_url

            # Get source location (warehouse stock location)
            source_location = False
            if order.session_id and order.session_id.config_id and order.session_id.config_id.warehouse_id:
                source_location = order.session_id.config_id.warehouse_id.lot_stock_id
            if not source_location:
                # fallback: try company's warehouse (may be None depending on your setup)
                company_wh = getattr(order.company_id, 'warehouse_id', False)
                source_location = company_wh.lot_stock_id if company_wh else False

            if not source_location:
                raise UserError(
                    "Source warehouse stock location not found. Please configure a warehouse with a stock location.")

            # Create a stock picking (one per line as previous behavior)
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': source_location.id,
                'location_dest_id': cutting_location.id,
                'origin': order.name,
            })

            # Create stock move
            move = self.env['stock.move'].create({
                'name': product.name,
                'product_id': product.id,
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id,
                'location_id': source_location.id,
                'location_dest_id': cutting_location.id,
            })

            # Reserve stock and validate the picking
            picking.action_assign()
            # If you need to set quantity_done on move lines, uncomment and adjust:
            # for move_line in picking.move_line_ids:
            #     move_line.quantity_done = quantity

            picking.button_validate()

        return order
