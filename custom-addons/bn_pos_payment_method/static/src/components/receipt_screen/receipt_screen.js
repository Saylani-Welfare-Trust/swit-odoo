/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";

patch(ReceiptScreen.prototype, {
    orderDone() {
        this.pos.removeOrder(this.currentOrder);
        this._addNewOrder();
        this.pos.resetProductScreenSearch();
        const { name, props } = this.nextScreen;
        
        if (this.pos.addedOtherInfo) {
            this.pos.addedOtherInfo = false
        }
        if (this.pos.pos_cheque_order_id) {
            this.pos.pos_cheque_order_id = false
        }
        if (this.pos.receive_voucher) {
            this.pos.receive_voucher = false
        }
        
        this.pos.showScreen(name, props);
    }
});
