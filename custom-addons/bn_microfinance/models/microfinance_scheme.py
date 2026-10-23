from odoo import models, fields, api


installment_selection = [
    ('daily', 'Daily'),
    ('monthly', 'Monthly')
]


class MicrofinanceScheme(models.Model):
    _name = 'microfinance.scheme'
    _description = "Microfinance Scheme"
    _inherit = ["mail.thread", "mail.activity.mixin"]


    name = fields.Char('Name', tracking=True)
    prefix = fields.Char('Prefix', tracking=True)
    
    is_created = fields.Boolean('Is Created', tracking=True)

    installment_type = fields.Selection(selection=installment_selection, string='Installment Type', default='daily', tracking=True)

    daily_recovery_days = fields.Integer('Recovery Days', default=0, tracking=True)
    monthly_recovery_days = fields.Integer('Recovery Days', default=0, tracking=True)

    microfinance_scheme_line_ids = fields.One2many('microfinance.scheme.line', 'microfinance_scheme_id', string="Microfinance Scheme Line")

    @api.model
    def create(self, vals):
        # vals['is_created'] = True
        record = super(MicrofinanceScheme, self).create(vals)

        self.env['ir.sequence'].create({
            'name': f"{record.name} Sequence",
            'code': f"microfinance.{record.id}",
            'padding': 7,
            'prefix': record.prefix,
        })

        return record

    def write(self, vals):
        record = super(MicrofinanceScheme, self).write(vals)
        
        seq_record = self.env['ir.sequence'].search([('code', '=', f"microfinance.{self.id}")])
        
        seq_record.write({'prefix': self.prefix})
        
        return record