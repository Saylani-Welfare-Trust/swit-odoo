from odoo import models, fields, api


class WelfareFieldsWizard(models.TransientModel):
    _inherit = 'welfare.fields.wizard'

    # Institution Details
    institution_category = fields.Selection([
        ('masjid', 'Masjid'),
        ('madrasa', 'Madrasa'),
    ], string='Institution Category')
    subcategory = fields.Char(string='Subcategory')

    committee_members_html = fields.Html(string='Committee Members', readonly=True)

    @api.model
    def default_get(self, fields_list):
        # institution_category / subcategory are copied from welfare by super()
        res = super().default_get(fields_list)
        welfare_id = self.env.context.get('active_id')
        if welfare_id:
            welfare = self.env['welfare'].browse(welfare_id)

            # Committee Members
            if welfare.committee_member_ids:
                html = '<table class="table" style="width:100%; border-collapse: collapse;">'
                html += '<thead><tr style="background-color: #f0f0f0;">'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Member</th>'
                html += '<th style="border: 1px solid #ddd; padding: 8px;">Role</th>'
                html += '</tr></thead><tbody>'
                for member in welfare.committee_member_ids:
                    html += '<tr>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;">{member.display_name}</td>'
                    html += f'<td style="border: 1px solid #ddd; padding: 8px;"></td>'
                    html += '</tr>'
                html += '</tbody></table>'
                res['committee_members_html'] = html
            else:
                res['committee_members_html'] = '<p>No committee members</p>'

        return res

    def _write_institution_fields(self):
        self.welfare_id.write({
            'institution_category': self.institution_category,
            'subcategory': self.subcategory,
        })

    def action_approve(self):
        self.ensure_one()
        self._write_institution_fields()
        return super().action_approve()

    def action_save_and_close(self):
        self.ensure_one()
        self._write_institution_fields()
        return super().action_save_and_close()
