from odoo import models, fields


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    is_medical_recovery = fields.Boolean('Is Medical Recovery')

    def button_validate(self):
        if self.is_medical_recovery:
            medical_equipment = self.env['medical.equipment'].search([
                ('name', '=', self.origin),
                ('state', '=', 'waiting_for_inventory_approval')
            ], limit=1)

            if medical_equipment:
                medical_equipment.state = 'recovered'

        super(StockPicking, self).button_validate()