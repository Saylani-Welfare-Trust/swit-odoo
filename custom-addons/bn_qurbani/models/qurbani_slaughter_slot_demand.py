from odoo import models, fields, api
from odoo.exceptions import UserError


class QurbaniSlaughterSlotDemand(models.Model):
    _name = "qurbani.slaughter.slot.demand"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Qurbani Slaughter Slot Demand"

    
    day_id = fields.Many2one("qurbani.day", string="Day", tracking=True)
    hijri_id = fields.Many2one("hijri", string="Hijri", tracking=True)
    slaughter_location_id = fields.Many2one('stock.location', string="Slaughter Location", tracking=True)
    inventory_product_id = fields.Many2one('product.product', string='Inventory Product', tracking=True)

    start_time = fields.Float(string="Start Time", tracking=True)
    end_time = fields.Float(string="End Time", tracking=True)

    slaughter_remaining_demand = fields.Integer('Slaughter Demand', compute="_compute_slaughter_remaining_demand")
    demand = fields.Integer(string="Demand", tracking=True)
    total_demand = fields.Integer('Cumulative Demand', compute="_compute_total_demand", store=True, tracking=True)
    remaining_demand = fields.Integer('Remaining Demand', compute="_compute_remaining_demand", store=True, tracking=True)
    total_hissa = fields.Integer('Total Hissa', compute="_compute_total_hissa", store=True, tracking=True)
    booked_hissa = fields.Integer('Booked Hissa', default=0, tracking=True)
    current_hissa = fields.Integer('Current Hissa', default=0, tracking=True)
    remaining_hissa = fields.Integer('Remaining Hissa', compute="_compute_remaining_hissa", store=True, tracking=True)

    distribution_location_ids = fields.Many2many('stock.location', string="Distribution Locations")


    @api.depends('total_hissa', 'booked_hissa')
    def _compute_remaining_hissa(self):
        for record in self:
            record.remaining_hissa = record.total_hissa - record.booked_hissa

    @api.depends('demand')
    def _compute_total_hissa(self):
        for record in self:
            hissa_per_unit = 0

            if record.inventory_product_id:
                name = record.inventory_product_id.name.lower()

                if 'cow' in name:
                    hissa_per_unit = 7
                elif 'goat' in name:
                    hissa_per_unit = 1

            record.total_hissa = int(hissa_per_unit * record.total_demand)

    @api.depends('demand')
    def _compute_slaughter_remaining_demand(self):
        for record in self:
            slaughter_demand = self.env['qurbani.slaughter.demand'].search([
                ('day_id', '=', record.day_id.id),
                ('hijri_id', '=', record.hijri_id.id),
                ('slaughter_location_id', '=', record.slaughter_location_id.id),
                ('inventory_product_id', '=', record.inventory_product_id.id)
            ], limit=1)

            record.slaughter_remaining_demand = slaughter_demand.remaining_demand if slaughter_demand else 0

    @api.onchange('demand')
    def check_demand(self):
        for record in self:
            slaughter_demand = self.env['qurbani.slaughter.demand'].search([
                ('day_id', '=', record.day_id.id),
                ('hijri_id', '=', record.hijri_id.id),
                ('slaughter_location_id', '=', record.slaughter_location_id.id),
                ('inventory_product_id', '=', record.inventory_product_id.id),
            ], limit=1)

            if not slaughter_demand:
                raise UserError("No slaughter demand found for the selected day, hijri date, and slaughter location.")

            if slaughter_demand and record.demand > slaughter_demand.remaining_demand:
                raise UserError(f"Slaughter demand cannot exceed slaughter demand of {slaughter_demand.remaining_demand}.")
            
            slaughter_demand.remaining_demand -= record.demand
            
    # --------------------------------
    # CITY DEMAND COMPUTE
    # --------------------------------
    @api.depends('demand')
    def _compute_total_demand(self):
        for record in self:
            if record.demand > 0:
                record.total_demand += record.demand

    @api.depends('demand')
    def _compute_remaining_demand(self):
        for record in self:
            if record.demand < 0:
                if record.remaining_demand + record.demand >= 0:
                    record.remaining_demand += record.demand
                    record.total_demand += record.demand
                    hissa_per_unit = 0

                    if record.inventory_product_id:
                        name = record.inventory_product_id.name.lower()

                        if 'cow' in name:
                            hissa_per_unit = 7
                        elif 'goat' in name:
                            hissa_per_unit = 1

                    record.total_hissa = int(hissa_per_unit * record.total_demand)
            elif record.demand > 0:
                record.remaining_demand += record.demand

    # ==================================================
    # GET MODELS
    # ==================================================
    def _get_product_models(self):

        product_name = (self.inventory_product_id.name or "").lower()

        if 'cow' in product_name:
            return {
                'slaughter': self.env['qurbani.cow.slaughter'],
                'distribution': self.env['qurbani.cow.distribution'],
            }

        elif 'goat' in product_name:
            return {
                'slaughter': self.env['qurbani.goat.slaughter'],
                'distribution': self.env['qurbani.goat.distribution'],
            }

        raise UserError(_("Unknown product type! Define Cow or Goat."))


    # ==================================================
    # GET DEMANDS
    # ==================================================
    def _get_demands(self, record):

        Demand = self.env['qurbani.slaughter.slot.demand']

        demands = Demand.search([
            ('day_id', '=', record.day_id.id),
            ('hijri_id', '=', record.hijri_id.id),
            ('slaughter_location_id', '=', record.slaughter_location_id.id),
            ('inventory_product_id', '=', record.inventory_product_id.id),
        ])

        if not demands:
            raise UserError(_("No demand record found!"))

        return demands


    # ==================================================
    # UPDATE DEMAND
    # ==================================================
    def update_demand(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Update Demand',
            'res_model': 'update.qurbani.demand',
            'view_mode': 'form',
            'view_id': self.env.ref('bn_profile_management.microfinance_application_wizard_form').id,
            'target': 'new',
            'context': {
                'default_qurbani_slaughter_slot_demand_id': self.id,
            }
        }

    def _update_demand(self):
        for record in self:

            if not record.inventory_product_id:
                continue

            models = record._get_product_models()

            SlaughterModel = models['slaughter']
            DistributionModel = models['distribution']

            demands = record._get_demands(record)

            for demand in demands:

                # ==================================================
                # SLAUGHTER RECORDS
                # ==================================================
                slaughter_records = SlaughterModel.search([
                    ('day_id', '=', demand.day_id.id),
                    ('hijri_id', '=', demand.hijri_id.id),
                    ('slaughter_location_id', '=', demand.slaughter_location_id.id),
                    ('inventory_product_id', '=', demand.inventory_product_id.id),
                    ('start_time', '=', demand.start_time),
                    ('end_time', '=', demand.end_time),
                ], order='id')

                required_slaughter = demand.total_demand or 0

                # ==================================================
                # SPLIT USED / FREE RECORDS
                # ==================================================
                used_slaughter_records = self.env[SlaughterModel._name]
                free_slaughter_records = self.env[SlaughterModel._name]

                for rec in slaughter_records:

                    has_lines = (
                        hasattr(rec, 'qurbani_cow_slaughter_line')
                        and rec.qurbani_cow_slaughter_line
                    )

                    has_order = (
                        hasattr(rec, 'qurbani_order_no')
                        and rec.qurbani_order_no
                    )

                    if has_lines or has_order:
                        used_slaughter_records += rec
                    else:
                        free_slaughter_records += rec

                total_existing_slaughter = len(slaughter_records)

                # ==================================================
                # CREATE SLAUGHTER
                # ==================================================
                if total_existing_slaughter < required_slaughter:

                    missing = required_slaughter - total_existing_slaughter

                    vals_list = []

                    for i in range(missing):
                        vals_list.append({
                            'day_id': demand.day_id.id,
                            'hijri_id': demand.hijri_id.id,
                            'slaughter_location_id': demand.slaughter_location_id.id,
                            'inventory_product_id': demand.inventory_product_id.id,
                            'start_time': demand.start_time,
                            'end_time': demand.end_time,
                        })

                    SlaughterModel.create(vals_list)

                # ==================================================
                # DELETE SLAUGHTER
                # ==================================================
                elif total_existing_slaughter > required_slaughter:

                    extra_count = (
                        total_existing_slaughter - required_slaughter
                    )

                    removable_records = free_slaughter_records[:extra_count]

                    if removable_records:
                        removable_records.unlink()

                # ==================================================
                # DISTRIBUTION RECORDS
                # ==================================================
                distribution_records = DistributionModel.search([
                    ('day_id', '=', demand.day_id.id),
                    ('hijri_id', '=', demand.hijri_id.id),
                    ('slaughter_location_id', '=', demand.slaughter_location_id.id),
                    ('inventory_product_id', '=', demand.inventory_product_id.id),
                    ('slaughter_start_time', '=', demand.start_time),
                    ('slaughter_end_time', '=', demand.end_time),
                ], order='id')

                required_distribution = demand.total_hissa or 0

                # ==================================================
                # SPLIT USED / FREE DISTRIBUTION
                # ==================================================
                used_distribution_records = distribution_records.filtered(
                    lambda r: r.qurbani_order_no
                )

                free_distribution_records = distribution_records.filtered(
                    lambda r: not r.qurbani_order_no
                )

                total_existing_distribution = len(distribution_records)

                # ==================================================
                # CREATE DISTRIBUTION
                # ==================================================
                if total_existing_distribution < required_distribution:

                    missing = (
                        required_distribution
                        - total_existing_distribution
                    )

                    vals_list = []

                    for i in range(missing):
                        vals_list.append({
                            'day_id': demand.day_id.id,
                            'hijri_id': demand.hijri_id.id,
                            'inventory_product_id': demand.inventory_product_id.id,
                            'slaughter_location_id': demand.slaughter_location_id.id,
                            'slaughter_start_time': demand.start_time,
                            'slaughter_end_time': demand.end_time,
                        })

                    DistributionModel.create(vals_list)

                # ==================================================
                # DELETE DISTRIBUTION
                # ==================================================
                elif total_existing_distribution > required_distribution:

                    extra_count = (
                        total_existing_distribution
                        - required_distribution
                    )

                    removable_records = (
                        free_distribution_records[:extra_count]
                    )

                    if removable_records:
                        removable_records.unlink()

    def action_open_chatter(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qurbani.slaughter.slot.demand',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }