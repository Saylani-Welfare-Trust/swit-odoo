from odoo import models, fields

class DirectDeposit(models.Model):
    _inherit = 'direct.deposit'


    qurbani_order_id = fields.Many2one('qurbani.order', string="Qurbani Order")


    def action_not_clear(self):
        for line in self.qurbani_order_id.qurbani_order_line_ids:
            distribution_schedule = self.env['distribution.schedule'].search([('day_id', '=', line.day_id.id), ('hijri_id', '=', line.hijri_id.id), ('pos_product_ids', 'in', [line.product_id.id]), ('start_time', '=', line.start_time), ('end_time', '=', line.end_time), ('location_id', '=', line.distribution_id.id)])

            if distribution_schedule:
                slaughter_slot_demand = self.env['qurbani.slaughter.slot.demand'].search([('day_id', '=', line.day_id.id), ('hijri_id', '=', line.hijri_id.id), ('inventory_product_id', '=', distribution_schedule.inventory_product_id.id), ('end_time', '=', distribution_schedule.slaughter_schedule_id.end_time), ('slaughter_location_id', '=', distribution_schedule.slaughter_location_id.id)])

                if slaughter_slot_demand:
                    slaughter_slot_demand.booked_hissa -= line.quantity
                    slaughter_slot_demand.current_hissa -= line.quantity
                    slaughter_slot_demand.remaining_hissa += line.quantity
            
            line.unlink()

        super(DirectDeposit, self).action_not_clear()

    @api.model
    def create_dd_record(self, data):
        address = data.get('address')
        bank_id = data.get('bank_id')
        service_charges = data.get('service_charges')
        user_id = data.get('user_id') or self.env.user.id
        transaction_ref = data.get('transaction_ref')

        # -------------------------
        # 1. Prepare Line Items
        # -------------------------
        product_lines = []
        for line in data['order_lines']:
            product_lines.append((0, 0, {
                'product_id': line['product_id'],
                'quantity': line['quantity'],
                'amount': line['price'],
                'remarks': line['remarks'] if line.get('remarks') else '',
            }))

        # -------------------------
        # 2. Create DD Record
        # -------------------------
        dd = self.create({
            'donor_id': data['donor_id'],
            'bank_id': bank_id,
            'user_id': user_id,
            'address': address,
            'service_charges': service_charges,
            'transaction_ref': transaction_ref,
            'transfer_to_dhs': data.get('transfer_to_dhs', False),
            'direct_deposit_line_ids': product_lines,
        })

        # -------------------------
        # 3. Calculate prices & taxes for all lines
        # -------------------------
        for line in dd.direct_deposit_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price
            for tax in taxes:
                if tax.amount_type == 'percent':
                    total_price_incl_tax += base_price * (tax.amount / 100)
                else:
                    total_price_incl_tax += tax.amount

            if not line.amount:
                line.amount = total_price_incl_tax * line.quantity

        # -------------------------
        # 4. Recalculate totals
        # -------------------------
        dd.calculate_amount()
        dd.set_remarks()

        qurbani_details = self.env['qurbani.order'].create_qurbani_record(data)

        self.qurbani_order_id = qurbani_details.get('id')

        return {
            "status": "success",
            "id": dd.id
        }