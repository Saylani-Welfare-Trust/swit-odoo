/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

import {_t} from "@web/core/l10n/translation";


export class ReceivingPopup extends AbstractAwaitablePopup {
    static template = "bn_pos_custom_action.ReceivingPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        
        this.title = this.props.title || "Module Name";
        
        this.action_type = this.props.action_type
        this.placeholder = this.props.placeholder

        this.state = useState({
            record_number: "",
        });
    }

    updateRecordNumber(event) {
        this.state.record_number = event.target.value;
    }

    canCancel() {
        return true;
    }

    async cancel() {
        if (this.canCancel()) {
            super.cancel();
        }
    }

    async confirm(){
        const selectedOrder = this.pos.get_order();

        if (this.active_type === 'dhs') {
            return;
        } else if (this.active_type === 'me') {
            return;
        }
    }
}