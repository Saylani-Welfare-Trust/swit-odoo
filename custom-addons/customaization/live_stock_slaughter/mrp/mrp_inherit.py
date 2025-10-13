import datetime

from odoo import models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_assign222(self):
        print("[MRP] action_assign: start checking availability for MOs")
        res = super().action_assign()
        for production in self:
            print(
                f"[MRP] action_assign: processing MO #{production.id} for product {production.product_id.display_name}")
            # v17: quantity_done reflects reserved/picked amount
            shortage_moves = production.move_raw_ids.filtered(lambda m: m.is_quantity_done_editable < m.product_uom_qty)
            print(f"[MRP] action_assign: found {len(shortage_moves)} moves with shortage (done < required)")
            if shortage_moves:
                print("[MRP] action_assign: insufficient stock, finding alternatives...")
                alternatives = production._find_alternative_products_with_qty()
                print(f"[MRP] action_assign: found {len(alternatives)} alternative BOM(s)")
                if alternatives:
                    msg = _(
                        "Cannot manufacture %(prod)s with %(quant)s quantity due to insufficient stock.\n\nHowever, you can manufacture:") % {
                              'prod': production.product_id.display_name,
                              'quant': production.product_qty,
                          }
                    print("[MRP] action_assign: preparing UserError message with quantities")
                    for bom, max_runs in alternatives:
                        variant = bom.product_tmpl_id.product_variant_id
                        line = f"  • {variant.display_name}: up to {max_runs} unit(s)"
                        print(f"[MRP] action_assign: alternative -> {variant.display_name}, qty {max_runs}")
                        msg += "\n" + line
                    print("[MRP] action_assign: raising UserError with suggestions and quantities")
                    raise UserError(msg)
        print("[MRP] action_assign: completed without alternatives or raised error")
        return res

    def action_assign(self):
        res = super().action_assign()
        for production in self:
            shortage = production.move_raw_ids.filtered(lambda m: m.is_quantity_done_editable < m.product_uom_qty)
            if shortage:
                msg = _(
                    "Cannot manufacture %(prod)s (qty: %(qty)s) due to insufficient stock.\n\nHowever, you can manufacture:") % {
                          'prod': production.product_id.display_name,
                          'qty': production.product_qty,
                      }
                alts = production._find_alternative_products_with_qty()
                if alts:
                    # 1) create the wizard record
                    wiz = self.env['mrp.alternative.wizard'].create({
                        'mo_id': production.id,
                        'message': msg,
                    })
                    # 2) create its line records
                    for bom, runs in alts:
                        self.env['mrp.alternative.line'].create({
                            'wizard_id': wiz.id,
                            'bom_id': bom.id,
                            'max_qty': runs,
                        })
                    # 3) return an action opening that specific wizard
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'mrp.alternative.wizard',
                        'view_mode': 'form',
                        'res_id': wiz.id,
                        'target': 'new',
                    }
                else:
                    raise UserError(msg)
        return res

    def _find_alternative_products_with_qty(self):
        """
        Return list of (bom, max_runs) for BOMs whose all components are in stock,
        computing the maximum number of runs given current inventory.
        """
        print("[MRP] _find_alternative_products_with_qty: searching BOMs with lines")
        boms = self.env['mrp.bom'].search([('bom_line_ids', '!=', False)])
        print(f"[MRP] _find_alternative_products_with_qty: {len(boms)} BOM(s) retrieved to evaluate")
        results = []
        for bom in boms:
            # compute runs = min(qty_available // required_qty) across all lines
            runs_per_line = []
            for line in bom.bom_line_ids:
                avail = line.product_id.qty_available
                required = line.product_qty
                if avail < required:
                    runs_per_line = []
                    break
                runs_per_line.append(avail // required)
            if runs_per_line:
                max_runs = min(runs_per_line)
                print(f"[MRP] _find_alternative_products_with_qty: BOM {bom.id} can run {max_runs} time(s)")
                results.append((bom, max_runs))
        print(f"[MRP] _find_alternative_products_with_qty: {len(results)} BOM(s) can be manufactured with quantities")
        return results


# models/mrp_production_alternative_wizard.py
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpAlternativeLine(models.TransientModel):
    _name = 'mrp.alternative.line'
    _description = 'Alternative Production Line'

    wizard_id = fields.Many2one('mrp.alternative.wizard', string='Wizard', required=True, store=True)
    bom_id = fields.Many2one('mrp.bom', string='Bill of Materials', store=True)
    product_id = fields.Many2one('product.product', related='bom_id.product_tmpl_id.product_variant_id', store=True)
    produce_qty = fields.Float(string='Quantity to Produce',related='bom_id.product_qty', required=True)

    max_qty = fields.Integer(string='Max Runs', store=True)
    selected = fields.Boolean(string='Select', store=True)

    @api.onchange('max_qty')
    def _check_produce_qty(self):
        for rec in self:
            if rec.produce_qty > rec.max_qty:
                raise ValidationError(
                    _("You cannot produce more than %s unit(s) for %s") % (rec.max_qty, rec.product_id.display_name))
            if rec.produce_qty <= 0:
                raise ValidationError(_("Production quantity must be at least 1"))


class MrpAlternativeWizard(models.TransientModel):
    _name = 'mrp.alternative.wizard'
    _description = 'Wizard to choose alternative production'

    mo_id = fields.Many2one('mrp.production', string='Original MO', readonly=True)
    message = fields.Text(string='Info', readonly=True)
    line_ids = fields.One2many('mrp.alternative.line', 'wizard_id', string='Alternatives')

    def action_confirm(self):
        Production = self.env['mrp.production']
        created_ids = []
        for wiz in self:
            sel = wiz.line_ids.filtered('selected')
            if not sel:
                raise UserError(_('Please select at least one alternative.'))
            for line in sel:
                # build default vals and override
                vals = Production.default_get(Production._fields.keys())
                vals.update({
                    'product_id': line.product_id.id,
                    'bom_id': line.bom_id.id,
                    'product_qty': line.max_qty,
                    'product_uom_id': line.product_id.uom_id.id,
                    'picking_type_id': wiz.mo_id.picking_type_id.id,
                    'location_src_id': wiz.mo_id.location_src_id.id,
                    'location_dest_id': wiz.mo_id.location_dest_id.id,
                    'company_id': wiz.mo_id.company_id.id,
                    'date_start': datetime.datetime.now(),
                    # 'date_finished': wiz.mo_id.date_finished,
                })
                new_mo = Production.create(vals)
                created_ids.append(new_mo.id)
        # open the newly created MOs
        if created_ids:
            return {
                'name': _('New Manufacturing Orders'),
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', created_ids)],
            }
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm_mrp(self):
        Production = self.env['mrp.production']
        created_ids = []
        for wiz in self:
            sel = wiz.line_ids.filtered('selected')
            if not sel:
                raise UserError(_('Please select at least one alternative.'))
            for line in sel:
                # pull in all defaults and override
                vals = Production.default_get(Production._fields.keys())
                vals.update({
                    'product_id': line.product_id.id,
                    'bom_id': line.bom_id.id,
                    'product_qty': line.max_qty,
                    'product_uom_id': line.product_id.uom_id.id,
                    'picking_type_id': wiz.mo_id.picking_type_id.id,
                    'location_src_id': wiz.mo_id.location_src_id.id,
                    'location_dest_id': wiz.mo_id.location_dest_id.id,
                    'company_id': wiz.mo_id.company_id.id,
                    'date_start': datetime.datetime.now(),
                    # 'date_finished': wiz.mo_id.date_finished,
                })
                new_mo = Production.create(vals)
                new_mo.action_confirm()
                created_ids.append(new_mo.id)
        # if we created any, open them in a tree+form view
        if created_ids:
            return {
                'name': _('New Manufacturing Orders'),
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.production',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', created_ids)],
                'context': {'search_default_filter_to_confirm': 1},
            }
        return {'type': 'ir.actions.act_window_close'}

# To launch the wizard from your action_assign instead of UserError:
# return self.env.ref('your_module.action_mrp_alternative_wizard').read()[0]
