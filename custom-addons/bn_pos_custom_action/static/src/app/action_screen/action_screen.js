/** @odoo-module */

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";

export class ActionScreen extends AbstractAwaitablePopup {
    static template = "bn_pos_custom_action.ActionScreen";

    setup() {
        super.setup();
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        // Own the numpad buffer while open, so stray keystrokes can't edit the order line underneath
        useService("number_buffer").use();
    }

    canCancel() {
        return true;
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }

    /**
     * Open the popup of an action and close this Actions menu once it is done:
     * confirmed, or the order was recorded and replaced by a new one (the
     * popups close themselves that way on success).
     */
    async openActionPopup(Popup, props) {
        const order = this.pos.get_order();
        const { confirmed } = await this.popup.add(Popup, props);
        if (confirmed || this.pos.get_order() !== order) {
            this.cancel();
        }
    }

    prepareOrderLines(orderLines) {
        return orderLines.map(line => ({
            product_id: line.product.id,
            quantity: line.quantity,
            price: line.price,
            qurbani_schedule: line.qurbani_schedule || null,
            remarks: line.customerNote,
        }));
    }
}