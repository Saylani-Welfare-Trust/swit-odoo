from odoo import models, fields, api


class DonationHomeService(models.Model):
    _inherit = 'donation.home.service'


    qurbani_order_id = fields.Many2one('qurbani.order', string='Qurbani Order')


    def action_cancel(self):
        for line in self.qurbani_order_id.qurbani_order_line_ids:
            distribution_schedule = self.env['distribution.schedule'].search([('day_id', '=', line.day_id.id), ('hijri_id', '=', line.hijri_id.id), ('pos_product_ids', 'in', [line.product_id.id]), ('start_time', '=', line.start_time), ('end_time', '=', line.end_time), ('location_id', '=', line.distribution_id.id)])

            if distribution_schedule:
                slaughter_slot_demand = self.env['qurbani.slaughter.slot.demand'].search([('day_id', '=', line.day_id.id), ('hijri_id', '=', line.hijri_id.id), ('inventory_product_id', '=', distribution_schedule.inventory_product_id.id), ('end_time', '=', distribution_schedule.slaughter_schedule_id.end_time), ('slaughter_location_id', '=', distribution_schedule.slaughter_location_id.id)])

                if slaughter_slot_demand:
                    slaughter_slot_demand.booked_hissa -= line.quantity
                    slaughter_slot_demand.current_hissa -= line.quantity
                    slaughter_slot_demand.remaining_hissa += line.quantity
            
            line.unlink()

        super(DonationHomeService, self).action_cancel()

    @api.model
    def create_dhs_record(self, data):
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
        # 2. Create DHS Record
        # -------------------------
        dhs = self.env['donation.home.service'].create({
            'donor_id': data['donor_id'],
            'address': data['address'],
            'service_charges': data['service_charges'],
            'donation_home_service_line_ids': product_lines,
        })

        # -------------------------
        # 3. Check if ALL lines are service products
        # -------------------------
        all_service = all(
            line.product_id.detailed_type == 'service'
            for line in dhs.donation_home_service_line_ids
        )

        if all_service:
            dhs.state = 'gate_in'     # ✔ only if 100% service lines

        # -------------------------
        # 4. Calculate prices & taxes for all lines
        # -------------------------
        for line in dhs.donation_home_service_line_ids:
            base_price = line.product_id.lst_price
            taxes = line.product_id.taxes_id

            total_price_incl_tax = base_price
            for tax in taxes:
                if tax.amount_type == 'percent':
                    total_price_incl_tax += base_price * (tax.amount / 100)
                else:
                    total_price_incl_tax += tax.amount

            if not line.amount:
                line.amount = total_price_incl_tax

        # -------------------------
        # 5. Recalculate totals
        # -------------------------
        dhs.calculate_amount()
        dhs.set_remarks()
        dhs.calculate_service_charges()

        qurbani_details = self.env['qurbani.order'].create_qurbani_record(data)

        dhs.qurbani_order_id = qurbani_details.get('id')

        return {
            "status": "success",
            "id": dhs.id,
        }