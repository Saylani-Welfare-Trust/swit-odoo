/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

const ORDER_TRANSFER_MODIFIER = "context.get('hide_order_transfer', False)";

export class LivestockSlaughterListController extends ListController {
    /** Order Transfer shows only when every selected line can be transferred. */
    evalViewModifier(modifier) {
        if (modifier === ORDER_TRANSFER_MODIFIER) {
            const selection = this.model.root.selection;
            return !selection.length || selection.some(
                (record) => record.data.state !== "slaughtered" || record.data.transfer_bool
            );
        }
        return super.evalViewModifier(modifier);
    }
}

registry.category("views").add("livestock_slaughter_list", {
    ...listView,
    Controller: LivestockSlaughterListController,
});
