from odoo import models, fields, api


class MicrofinanceFamily(models.Model):
    _name = 'microfinance.family'
    _description = "Microfinance Family"


    relation = fields.Char('Relation')
    education = fields.Char('Education')
    complete_name = fields.Char('Complete Name')
    monthly_income = fields.Char('Monthly Income')
    cnic_no = fields.Char('CNIC No')
    age = fields.Integer('Age')

    cnic_b_form = fields.Binary('CNIC / B Form')
    cnic_b_form_name = fields.Char('CNIC / B Form Name')

    microfinance_id = fields.Many2one('microfinance', string="Microfinance")
    
    # Related welfare records linked by CNIC (computed)
    welfare_count = fields.Integer(
        string="Welfare Records Count",
        compute='_compute_welfare_ids',
        store=False
    )
    
    @api.depends('cnic_no')
    def _compute_welfare_ids(self):
        """Search for welfare records with matching CNIC number"""
        for record in self:
            if record.cnic_no:
                # Search for welfare records where cnic_no matches
                welfare_records = self.env['welfare'].search([
                    ('cnic_no', '=', record.cnic_no)
                ])
                record.welfare_count = len(welfare_records)
            else:
                record.welfare_count = 0
    
    def get_related_welfare_records(self):
        """Get all welfare records with matching CNIC"""
        if self.cnic_no:
            return self.env['welfare'].search([
                ('cnic_no', '=', self.cnic_no)
            ])
        return self.env['welfare'].browse()
    
    def action_open_welfare(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Welfare Records',
            'res_model': 'welfare',  # your actual model
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.welfare_ids.ids)],
            'target': 'current',
        }