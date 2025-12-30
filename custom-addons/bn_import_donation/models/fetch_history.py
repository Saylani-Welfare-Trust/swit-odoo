from odoo import models, fields


class FetchHistory(models.Model):
    _name = 'fetch.history'
    _description = "Fetch History"


    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    journal_entry_id = fields.Many2one('account.move', string="Journal Entry")
    picking_id = fields.Many2one('stock.picking', string="Picking")


    def show_stock_picking(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'target': 'current',
        }

    def show_journal_entry(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Journal Entry',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.journal_entry_id.id,
            'target': 'current',
        }
    
    def show_fetch_donation(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fetch Donation',
            'res_model': 'api.donation',
            'view_mode': 'tree,form',
            'domain': [('fetch_history_id', '=', self.id)],
            'target': 'current',
        }