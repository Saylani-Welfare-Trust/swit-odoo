/** @odoo-module */

import { onMounted } from "@odoo/owl";
import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { patch } from "@web/core/utils/patch";

// "Close Session" on the Medical & Health > Counters card opens the counter with ?mh_close=1:
// go straight to the closing screen, the same as the menu's Close Session
patch(Navbar.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            const params = new URLSearchParams(window.location.search);
            if (!params.has("mh_close")) {
                return;
            }
            // only once: not again when the page is reloaded
            params.delete("mh_close");
            window.history.replaceState(window.history.state, "", `${window.location.pathname}?${params}`);
            if (this.pos.config.is_medical_pos) {
                this.closeSession();
            }
        });
    },
});
