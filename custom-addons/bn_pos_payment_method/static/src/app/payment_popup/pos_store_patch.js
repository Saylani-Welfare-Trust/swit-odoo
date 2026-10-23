/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    async after_load_server_data() {
        const res = await super.after_load_server_data(...arguments);
        await this.preloadBanks();
        return res;
    },

    async preloadBanks() {
        try {
            const banks = await this.orm.call("bank", "get_banks", []);
            localStorage.setItem("pos_bank_list", JSON.stringify(banks));
        } catch (error) {
            // Session is opening offline or the call failed — nothing to do,
            // the popup will fall back to any previously cached list.
            console.warn("Could not preload bank list for offline use", error);
        }
    },
});