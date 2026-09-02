/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import {
    putCustomers,
    getLastSync,
    setLastSync,
} from "./customer_offline_db";

const CHUNK_LIMIT = 5000;

patch(PosStore.prototype, {
    async after_load_server_data() {
        const res = await super.after_load_server_data(...arguments);
        // Runs once per session open, while the POS is (presumably)
        // still online. Does not block the cashier from starting the
        // session — errors are swallowed so a slow/failed sync never
        // prevents opening the register.
        this.syncCustomersLight();
        return res;
    },

    async syncCustomersLight() {
        const lastSync = getLastSync();
        let offset = 0;
        let latestServerTime = lastSync;

        try {
            // eslint-disable-next-line no-constant-condition
            while (true) {
                const result = await this.orm.call(
                    "res.partner",
                    "get_pos_customers_light",
                    [],
                    { offset, limit: CHUNK_LIMIT, last_sync: lastSync }
                );
                const { partners, server_time } = result;
                latestServerTime = server_time;

                if (!partners.length) {
                    break;
                }

                await putCustomers(partners);
                offset += CHUNK_LIMIT;

                if (partners.length < CHUNK_LIMIT) {
                    break;
                }
            }
            setLastSync(latestServerTime);
        } catch (error) {
            // Offline at session-open time, or the call failed. Whatever
            // was cached from a previous sync stays available; nothing
            // to do here except leave a trace for debugging.
            console.warn(
                "[pos_offline_customers] Customer sync skipped (offline or failed):",
                error
            );
        }
    },
});
