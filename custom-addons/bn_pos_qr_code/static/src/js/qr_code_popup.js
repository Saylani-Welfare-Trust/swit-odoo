/** @odoo-module **/
/**
 * Defines AbstractAwaitablePopup extending from AbstractAwaitablePopup
 */
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { _lt } from '@web/core/l10n/translation';

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";

import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";

class QRCode extends AbstractAwaitablePopup {
    setup() {
        super.setup();

        this.pos = usePos();
        this.popup = useService("popup");
        this.qrCode = ""
        this.transactionID = ""
    }

    onQRCode(event) {
        this.qrCode = event.target.value;
    }
    
    onTransactionID(event) {
        this.transactionID = event.target.value;
    }

    async confirmTransaction() {
        const order = this.pos.get_order();
        
        if (!order) {
            this.popup.add(ErrorPopup, {
                title: _t("Error"),
                body: "Order not Found",
            });
            return;
        }

        console.log(this.transactionID);
        console.log(this.qrCode);
        console.log(order);
        
        order.set_transaction_id(this.transactionID)
        order.set_qr_code(this.qrCode)
        this.cancel();
    }    

    getPayload() {
        return {
            qrCode: this.qrCode,
            transactionID: this.transactionID,
        };
    }
}
QRCode.template = 'QRCode';
QRCode.defaultProps = {
    confirmText: _lt('Ok'),
    cancelText: _lt('Cancel'),
    title: '',
    body: '',
};
export default QRCode;
