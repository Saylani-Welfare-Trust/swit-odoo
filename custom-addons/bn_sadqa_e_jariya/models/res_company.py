from odoo import models, fields


def portal_setting(name, string, default=False):
    """Char field kept in the System Parameter bn_sadqa_e_jariya.<name>, not a res_company column:
    res.company is read on every request, so a new column breaks the whole instance when the code is
    deployed before the module is upgraded. Each field has its own compute / inverse, saving one of
    them must not rewrite the others."""
    key = f'bn_sadqa_e_jariya.{name}'

    def compute(records):
        value = records.env['ir.config_parameter'].sudo().get_param(key) or default
        for company in records:
            company[name] = value

    def inverse(records):
        for company in records:
            records.env['ir.config_parameter'].sudo().set_param(key, company[name] or False)

    return fields.Char(string, compute=compute, inverse=inverse)


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Institution portal: Send Form / Check Portal Status / Send for Inquiry
    # (endpoints are appended to welfare_instituiton_url)
    institution_portal_login_url = portal_setting('institution_portal_login_url', 'Institution Portal Login URL')
    # Donee logins are <donee name>.<form number>@<this domain>
    institution_portal_email_domain = portal_setting('institution_portal_email_domain', 'Portal Login Email Domain')
    create_institution_account_endpoint = portal_setting('create_institution_account_endpoint', 'Create Institution Account Endpoint')
    institution_application_status_endpoint = portal_setting('institution_application_status_endpoint', 'Institution Application Status Endpoint')
    assign_institution_inquiry_endpoint = portal_setting('assign_institution_inquiry_endpoint', 'Assign Institution Inquiry Officer Endpoint')

    # Approved WhatsApp template, body: {{1}} donee name, {{2}} portal link, {{3}} login email, {{4}} password
    institution_login_whatsapp_template = portal_setting('institution_login_whatsapp_template', 'Portal Login WhatsApp Template')
    institution_login_whatsapp_namespace = portal_setting('institution_login_whatsapp_namespace', 'Portal Login WhatsApp Namespace')
    institution_login_whatsapp_language = portal_setting('institution_login_whatsapp_language', 'Portal Login WhatsApp Language', default='en')
