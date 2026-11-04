from markupsafe import escape

from odoo import models, fields, api


class SadqaJariyaDisbursementCategory(models.Model):
    _name = 'sadqa.jariya.disbursement.category'
    _description = 'Sadqa e Jariya Disbursement Category'

    # 'Cash' and 'In Kind' drive the payout (bills / deliveries), matched by name
    name = fields.Char('Name', required=True)


class SadqaJariyaArea(models.Model):
    _name = 'sadqa.jariya.area'
    _description = 'Sadqa e Jariya Area'
    _order = 'name'

    name = fields.Char('Name', required=True)
    code = fields.Char('Area Code')
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True)


class SadqaJariyaApplicationType(models.Model):
    _name = 'sadqa.jariya.application.type'
    _description = 'Sadqa e Jariya Disbursement Application Type'

    name = fields.Char('Name', required=True)
    order_type = fields.Selection([
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
        ('both', 'Both'),
    ], string='Order Type')
    product_category_id = fields.Many2one('product.category', string='Product Category')
    disbursement_category_id = fields.Many2one('sadqa.jariya.disbursement.category', string='Disbursement Category')
    analytic_account_ids = fields.Many2many(
        'account.analytic.account',
        'sadqa_jariya_application_type_analytic_rel',
        'application_type_id',
        'analytic_account_id',
        string='Branch',
    )


class SadqaJariyaApprovalLimit(models.Model):
    _name = 'sadqa.jariya.approval.limit'
    _description = 'Sadqa e Jariya Approval Limit'
    _rec_name = 'group_id'

    group_id = fields.Many2one(
        'res.groups',
        string='User Group',
        required=True,
        default=lambda self: self.env.ref('bn_sadqa_e_jariya.group_sadqa_jariya_hod', raise_if_not_found=False),
    )
    max_amount_limit = fields.Monetary(string='Maximum Approval Amount', required=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id)
    allowed_product_ids = fields.Many2many(
        'product.product',
        'sadqa_jariya_approval_limit_product_rel',
        'limit_id',
        'product_id',
        string='Allowed Products',
        domain="[('product_tmpl_id.is_sadqa_jariya', '=', True)]",
    )
    active = fields.Boolean(string='Active', default=True)


class SadqaJariyaDocument(models.Model):
    _name = 'sadqa.jariya.document'
    _description = 'Sadqa e Jariya Document'

    application_id = fields.Many2one('sadqa.jariya', string='Application', required=True, ondelete='cascade')
    document_type = fields.Selection([
        ('application_form', 'Application Form'),
        ('cnic', 'CNIC'),
        ('registration', 'Registration / Ilhaq'),
        ('land_documents', 'Land Documents'),
        ('pictures', 'Pictures'),
        ('other', 'Other'),
    ], string='Document Type', required=True)
    image_data = fields.Binary('File', attachment=True)
    image_filename = fields.Char('Filename')
    source_url = fields.Char('Source URL')
    display_image = fields.Html(string='Preview', compute='_compute_display_image', sanitize=False)

    @api.depends('image_data', 'source_url', 'document_type')
    def _compute_display_image(self):
        labels = dict(self._fields['document_type'].selection)
        for rec in self:
            label = labels.get(rec.document_type, 'Document')
            if rec.image_data and isinstance(rec.id, int):
                rec.display_image = (
                    f'<a href="/web/content/sadqa.jariya.document/{rec.id}/image_data" target="_blank" '
                    f'class="btn btn-sm btn-primary">📄 View {label}</a>'
                )
            elif rec.source_url:
                rec.display_image = (
                    f'<a href="{escape(rec.source_url)}" target="_blank" class="btn btn-sm btn-info">🔗 View {label}</a>'
                )
            else:
                rec.display_image = '<span class="text-muted">❌ No File</span>'
