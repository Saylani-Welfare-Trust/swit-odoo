from odoo import models, fields
from odoo.addons.bn_sms_whatsapp.models.whatsapp_service import WHATSAPP_DEFAULTS

NAMESPACE = WHATSAPP_DEFAULTS['whatsapp_namespace']


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
    # (existing columns, kept with their names so the saved URL and key stay)
    welfare_instituiton_url = fields.Char('Welfare Institution URL', tracking=True)
    odoo_auth_institution_key = fields.Char('Odoo Auth Institution Key')
    institution_portal_login_url = portal_setting('institution_portal_login_url', 'Institution Portal Login URL')
    # A donee's permanent login, made on their first application: <donee name>.<form number>@<this domain>
    institution_portal_email_domain = portal_setting('institution_portal_email_domain', 'Portal Login Email Domain')

    # Optional approved WhatsApp template for the portal login (SMS without it),
    # body: {{1}} donee name, {{2}} portal link, {{3}} login email, {{4}} password
    institution_login_whatsapp_template = portal_setting('institution_login_whatsapp_template', 'Portal Login WhatsApp Template')
    institution_login_whatsapp_namespace = portal_setting('institution_login_whatsapp_namespace', 'Portal Login WhatsApp Namespace')
    institution_login_whatsapp_language = portal_setting('institution_login_whatsapp_language', 'Portal Login WhatsApp Language', default='en')

    # Approved WhatsApp template the donee's profile form PDF goes with (Send Profile Form):
    # Document header, fixed "profile registered" body; the namespace is the WhatsApp Business account's
    institution_profile_whatsapp_template = portal_setting('institution_profile_whatsapp_template', 'Profile Form WhatsApp Template')
    institution_profile_whatsapp_namespace = portal_setting('institution_profile_whatsapp_namespace', 'Profile Form WhatsApp Namespace', default=NAMESPACE)
    institution_profile_whatsapp_language = portal_setting('institution_profile_whatsapp_language', 'Profile Form WhatsApp Language', default='en')
