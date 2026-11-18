from odoo import api, models

AUDIT_GROUP = 'bn_purchase_audit.group_purchase_audit'


class AuditReadonlyFormMixin(models.AbstractModel):
    """ The Purchase / Audit group is read-only: on the forms it opens, the buttons of
    the header (Confirm, Send by Email, Receive Products, Validate, Create Bill, Cancel...)
    are removed, including those other modules add there. The status bar stays.

    Done here rather than with `groups="!..."` on the header in XML: the header holds the
    `state` field, which the rest of the form uses, so hiding the whole header fails the
    view validation. """
    _name = 'bn.audit.readonly.form.mixin'
    _description = 'Purchase Audit: no header buttons on forms'

    @api.model
    def _is_purchase_auditor(self):
        return self.env.user.has_group(AUDIT_GROUP)

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        # the view differs for the auditor, so it must be cached apart
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (view_type == 'form' and self._is_purchase_auditor(),)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form' and self._is_purchase_auditor():
            for button in arch.xpath('/form/header//button'):
                button.getparent().remove(button)
        return arch, view


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'bn.audit.readonly.form.mixin']


class PurchaseRequisition(models.Model):
    _name = 'purchase.requisition'
    _inherit = ['purchase.requisition', 'bn.audit.readonly.form.mixin']


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'bn.audit.readonly.form.mixin']


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'bn.audit.readonly.form.mixin']


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'bn.audit.readonly.form.mixin']


class MaterialRequest(models.Model):
    _name = 'material.request'
    _inherit = ['material.request', 'bn.audit.readonly.form.mixin']
