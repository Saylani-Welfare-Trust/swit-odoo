from odoo import models, fields

# Kept as System Parameters (bn_sadqa_e_jariya.<field>), not res_company columns: res.company is read on
# every request, so a new column breaks the whole instance when the code is deployed before the upgrade
PORTAL_SETTINGS = (
    'institution_portal_login_url',
    'create_institution_account_endpoint',
    'institution_application_status_endpoint',
    'assign_institution_inquiry_endpoint',
    'institution_login_whatsapp_template',
    'institution_login_whatsapp_namespace',
    'institution_login_whatsapp_language',
)


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Institution portal: Send Form / Check Portal Status / Send for Inquiry
    # (endpoints are appended to welfare_instituiton_url)
    institution_portal_login_url = fields.Char('Institution Portal Login URL', compute='_compute_portal_settings', inverse='_inverse_portal_settings')
    create_institution_account_endpoint = fields.Char('Create Institution Account Endpoint', compute='_compute_portal_settings', inverse='_inverse_portal_settings')
    institution_application_status_endpoint = fields.Char('Institution Application Status Endpoint', compute='_compute_portal_settings', inverse='_inverse_portal_settings')
    assign_institution_inquiry_endpoint = fields.Char('Assign Institution Inquiry Officer Endpoint', compute='_compute_portal_settings', inverse='_inverse_portal_settings')

    # Approved WhatsApp template, body: {{1}} donee name, {{2}} portal link, {{3}} email, {{4}} password
    institution_login_whatsapp_template = fields.Char('Portal Login WhatsApp Template', compute='_compute_portal_settings', inverse='_inverse_portal_settings')
    institution_login_whatsapp_namespace = fields.Char('Portal Login WhatsApp Namespace', compute='_compute_portal_settings', inverse='_inverse_portal_settings')
    institution_login_whatsapp_language = fields.Char('Portal Login WhatsApp Language', compute='_compute_portal_settings', inverse='_inverse_portal_settings')

    def _compute_portal_settings(self):
        params = self.env['ir.config_parameter'].sudo()
        for company in self:
            for name in PORTAL_SETTINGS:
                company[name] = params.get_param(f'bn_sadqa_e_jariya.{name}', False)
            company.institution_login_whatsapp_language = company.institution_login_whatsapp_language or 'en'

    def _inverse_portal_settings(self):
        params = self.env['ir.config_parameter'].sudo()
        for company in self:
            for name in PORTAL_SETTINGS:
                params.set_param(f'bn_sadqa_e_jariya.{name}', company[name] or False)
