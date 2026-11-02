from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Institution portal: Send Form / Check Portal Status / Send for Inquiry
    # (endpoints are appended to welfare_instituiton_url)
    institution_portal_login_url = fields.Char('Institution Portal Login URL', tracking=True)
    create_institution_account_endpoint = fields.Char('Create Institution Account Endpoint', tracking=True)
    institution_application_status_endpoint = fields.Char('Institution Application Status Endpoint', tracking=True)
    assign_institution_inquiry_endpoint = fields.Char('Assign Institution Inquiry Officer Endpoint', tracking=True)

    # Approved WhatsApp template, body: {{1}} donee name, {{2}} portal link, {{3}} email, {{4}} password
    institution_login_whatsapp_template = fields.Char('Portal Login WhatsApp Template', tracking=True)
    institution_login_whatsapp_namespace = fields.Char('Portal Login WhatsApp Namespace', tracking=True)
    institution_login_whatsapp_language = fields.Char('Portal Login WhatsApp Language', default='en', tracking=True)
