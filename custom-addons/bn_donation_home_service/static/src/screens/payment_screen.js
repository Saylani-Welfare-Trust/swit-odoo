/** @odoo-module **/

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    async validateOrder(isForceValidate) {
        const currentOrder = this.currentOrder;
        
        currentOrder.extra_data ||= {};
        
        const dhsData = currentOrder.extra_data.dhs;
                
        if (dhsData && dhsData.dhs_id) {
            currentOrder.set_source_document(dhsData.record_number)
        }
        
        // Continue with normal POS flow
        super.validateOrder(isForceValidate);
    },
});