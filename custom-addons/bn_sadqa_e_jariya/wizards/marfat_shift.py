from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SadqaJariyaMarfatShift(models.TransientModel):
    _name = 'sadqa.jariya.marfat.shift'
    _description = 'Check Sadqa e Jariya Assigned Officer (Marfat) Shift'

    assigned_officer_id = fields.Many2one(
        'hr.employee',
        string='Assigned Officer (Marfat)',
        default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1),
        readonly=True,
    )
    line_ids = fields.Many2many('sadqa.jariya.line', string='Disbursement Lines', compute='_compute_lines')
    recurring_line_ids = fields.Many2many('sadqa.jariya.recurring.line', string='Recurring Lines', compute='_compute_lines')

    @api.depends('assigned_officer_id')
    def _compute_lines(self):
        """Lines of the logged-in officer to collect today"""
        today = fields.Date.context_today(self)
        for rec in self:
            domain = [
                ('assigned_officer_id', '=', rec.assigned_officer_id.id),
                ('collection_date', '=', today),
                ('state', 'not in', ['disbursed']),
            ]
            rec.line_ids = self.env['sadqa.jariya.line'].search(domain) if rec.assigned_officer_id else False
            rec.recurring_line_ids = self.env['sadqa.jariya.recurring.line'].search(domain) if rec.assigned_officer_id else False

    def action_check_shift(self):
        if not self.assigned_officer_id:
            raise UserError(_("Your user is not linked to an employee (Assigned Officer)."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
