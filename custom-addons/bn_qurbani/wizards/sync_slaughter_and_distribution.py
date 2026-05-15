from odoo import models, fields
from datetime import datetime, time


class SyncSalughterAndDistribution(models.Model):
    _name = 'sync.slaughter.and.distribution'
    _description = "Sync Slaughter And Distribution"

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')


    def action_sync(self):

        start_datetime = datetime.combine(self.start_date, time.min)
        end_datetime = datetime.combine(self.end_date, time.max)

        orders = self.env['qurbani.order'].search([
            ('create_date', '>=', start_datetime),
            ('create_date', '<=', end_datetime),
            ('is_sync', '=', False)
        ])

        for order in orders:
            for line in order.qurbani_order_line_ids:

                product_name = (line.product_id.name or "").lower()

                # ==================================================
                # COW
                # ==================================================
                if 'cow' in product_name:

                    slaughter_records = self.env['qurbani.cow.slaughter'].search([
                        ('day_id', '=', line.day_id.id),
                        ('hijri_id', '=', line.hijri_id.id),
                        ('start_time', '=', line.slaughter_start_time),
                        ('end_time', '=', line.slaughter_end_time),
                        ('slaughter_location_id', '=', line.slaughter_id.id),
                        ('state', '!=', 'transfer'),
                    ], order='id asc')

                    qurbani_cow_slaughter = False

                    # PICK FIRST RECORD HAVING < 8 LINES
                    for rec in slaughter_records:

                        current_count = len(rec.qurbani_cow_slaughter_line)

                        if current_count < 7:
                            qurbani_cow_slaughter = rec
                            break

                    if not qurbani_cow_slaughter:
                        return {
                            "status": "error",
                            "body": "No empty cow slaughter slot available."
                        }

                    # APPEND LINE
                    qurbani_cow_slaughter.write({
                        'qurbani_cow_slaughter_line': [(0, 0, {
                            'qurbani_order_no': line.qurbani_order_id.name,
                            'qurbani_order_line_no': line.name,
                            'hissa_name': line.hissa_name,
                            'product_id': line.product_id.id,
                        })]
                    })

                    # UPDATE SLOT FULL
                    qurbani_cow_slaughter.slot_full = len(
                        qurbani_cow_slaughter.qurbani_cow_slaughter_line
                    )

                    # DISTRIBUTION
                    qurbani_cow_distribution = self.env['qurbani.cow.distribution'].search([
                        ('day_id', '=', line.day_id.id),
                        ('hijri_id', '=', line.hijri_id.id),
                        ('slaughter_start_time', '=', line.slaughter_start_time),
                        ('slaughter_end_time', '=', line.slaughter_end_time),
                        ('slaughter_location_id', '=', line.slaughter_id.id),
                        ('start_time', '=', line.start_time),
                        ('end_time', '=', line.end_time),
                        ('distribution_location_id', '=', line.distribution_id.id),
                        ('qurbani_order_no', '=', False),
                    ], limit=1)

                    if qurbani_cow_distribution:
                        qurbani_cow_distribution.write({
                            'qurbani_order_no': line.qurbani_order_id.name,
                            'qurbani_order_line_no': line.name,
                            'hissa_name': line.hissa_name,
                            'product_id': line.product_id.id,
                            'state': 'not_applicable' if 'no' in line.product_id.name.lower() else 'pending',
                        })

                # ==================================================
                # GOAT
                # ==================================================
                elif 'goat' in product_name:

                    qurbani_goat_slaughter = self.env['qurbani.goat.slaughter'].search([
                        ('day_id', '=', line.day_id.id),
                        ('hijri_id', '=', line.hijri_id.id),
                        ('start_time', '=', line.slaughter_start_time),
                        ('end_time', '=', line.slaughter_end_time),
                        ('slaughter_location_id', '=', line.slaughter_id.id),
                        ('qurbani_order_no', '=', False),
                        ('is_transfer', '=', False),
                    ], limit=1)

                    if qurbani_goat_slaughter:
                        qurbani_goat_slaughter.write({
                            'qurbani_order_no': line.qurbani_order_id.name,
                            'qurbani_order_line_no': line.name,
                            'hissa_name': line.hissa_name,
                            'product_id': line.product_id.id,
                        })

                    # DISTRIBUTION
                    qurbani_goat_distribution = self.env['qurbani.goat.distribution'].search([
                        ('day_id', '=', line.day_id.id),
                        ('hijri_id', '=', line.hijri_id.id),
                        ('slaughter_start_time', '=', line.slaughter_start_time),
                        ('slaughter_end_time', '=', line.slaughter_end_time),
                        ('slaughter_location_id', '=', line.slaughter_id.id),
                        ('start_time', '=', line.start_time),
                        ('end_time', '=', line.end_time),
                        ('distribution_location_id', '=', line.distribution_id.id),
                        ('qurbani_order_no', '=', False),
                    ], limit=1)

                    if qurbani_goat_distribution:
                        qurbani_goat_distribution.write({
                            'qurbani_order_no': line.qurbani_order_id.name,
                            'qurbani_order_line_no': line.name,
                            'hissa_name': line.hissa_name,
                            'product_id': line.product_id.id,
                            'state': 'not_applicable' if 'no' in line.product_id.name.lower() else 'pending',
                        })

            order.is_sync = True