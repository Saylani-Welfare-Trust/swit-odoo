/** @odoo-module **/

import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { usePos } from "@point_of_sale/app/store/pos_hook";

import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";

import {_t} from "@web/core/l10n/translation";


export class ProvisionalPopup extends AbstractAwaitablePopup {
    static template = "bn_pos_custom_action.ProvisionalPopup";

    setup() {
        this.pos = usePos();
        this.orm = useService("orm");
        this.popup = useService("popup");
        this.report = useService("report");
        this.notification = useService("notification");
        
        this.title = this.props.title || "Provisional Order Details";
        
        this.donor_id = this.props.donor_id;
        this.donor_name = this.props.donor_name;
        this.orderLines = this.props.orderLines;
        this.action_type = this.props.action_type;
        
        this.state = useState({
            amount: parseFloat(this.props.amount),
            service_charges: 0,
            total: parseFloat(this.props.amount),
            donor_address: this.props.donor_address || "",
        });
    }

    saveServiceCharger(event) {
        const service_charges = parseFloat(event.target.value)
        this.state.service_charges = service_charges;
        this.state.total = this.state.amount + service_charges
    }

    updateAddress(event) {
        this.state.donor_address = event.target.value;
    }

    prepareOrderLines(orderLines) {
        return orderLines.map(line => (
                {
                    product_id: line.product.id,
                    quantity: line.quantity,
                }
            )
        );
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

        if (this.action_type === 'dhs') {
            const payload ={
                'donor_id': this.donor_id,
                'address': this.state.donor_address,
                'service_charges': this.state.service_charges,
                'order_lines': this.prepareOrderLines(this.orderLines),
            }
    
            await this.orm.call('donation.home.service', "create_dhs_record", [payload]).then((data) => {
                if (data.status === 'success') {
                    this.notification.add(_t("Operation Successful"), {
                        type: "info",
                    });
    
                    this.cancel()
                    
                    this.report.doAction("bn_donation_home_service.report_donation_home_service", [
                        data.id,
                    ]);
                }
    
                this.pos.removeOrder(selectedOrder);
                this.pos.add_new_order();
            })
        }
    }
}