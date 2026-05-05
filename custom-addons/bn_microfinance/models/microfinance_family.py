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
    
    # Related welfare records linked by CNIC
    welfare_ids = fields.Many2many(
        'welfare',
        'microfinance_family_welfare_rel',
        'family_id',
        'welfare_id',
        string="Related Welfare Records",
        compute='_compute_welfare_ids',
        store=False
    )
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
                record.welfare_ids = welfare_records
                record.welfare_count = len(welfare_records)
            else:
                record.welfare_ids = False
                record.welfare_count = 0

    
    
    
    