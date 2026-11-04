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

    # Institution portal: operations are POSTed to welfare_instituiton_url + /rpc/odoo/institutional/<operation>
    institution_portal_login_url = portal_setting('institution_portal_login_url', 'Institution Portal Login URL')
    # A donee's permanent login, made on their first application: <donee name>.<form number>@<this domain>
    institution_portal_email_domain = portal_setting('institution_portal_email_domain', 'Portal Login Email Domain')

    # Optional approved WhatsApp template for the portal login (SMS without it),
    # body: {{1}} donee name, {{2}} portal link, {{3}} login email, {{4}} password
    institution_login_whatsapp_template = portal_setting('institution_login_whatsapp_template', 'Portal Login WhatsApp Template')
    institution_login_whatsapp_namespace = portal_setting('institution_login_whatsapp_namespace', 'Portal Login WhatsApp Namespace')
    institution_login_whatsapp_language = portal_setting('institution_login_whatsapp_language', 'Portal Login WhatsApp Language', default='en')

    # Service product (available in POS) the cashier pays applications with, like Welfare's welfare_product
    sadqa_jariya_pos_product = portal_setting('sadqa_jariya_pos_product', 'Sadqa e Jariya POS Product')
