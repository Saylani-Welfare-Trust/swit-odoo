/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

patch(WebClient.prototype, {
    setup() {
        super.setup();

        setTimeout(() => {
            if (!document.querySelector(".saylani-banner")) {
                const banner = document.createElement("div");

                banner.className = "saylani-banner";


		banner.innerHTML = `
		    <img class="saylani-banner-img"
		    src="/saylani_erp_banner/static/src/img/supply_chain_banner.png?v=3"/>
		`;
			const target = document.querySelector(".o_web_client");

			if (target && !document.querySelector(".saylani-banner")) {
			    target.prepend(banner);
			}
            }
        }, 1000);
    },
});
