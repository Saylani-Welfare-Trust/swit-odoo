/** @odoo-module **/

import { onMounted } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { GenerateDialog } from "@stock/widgets/generate_serial";


patch(GenerateDialog.prototype, {
    setup(...args) {
        super.setup(...args);

        onMounted(async() => {
            console.log('working')
            console.log(this)
            if (this.props.type === "serial") {
                try {
                    // resId of the move (because you passed this.props.record as "move")
                    const moveId = this.props.move.resId;
                    const next = await this.orm.call(
                        "stock.move",
                        "get_next_sno",
                        [moveId]
                    );
                    if (this.nextSerial?.el) {
                        this.nextSerial.el.value = next || "";
                    }
                } catch (e) {
                    console.error("Failed to fetch next serial", e);
//                    if (this.nextSerial?.el) {
//                        this.nextSerial.el.value = "DO-CH-0001";
//                    }
                }
            }
        });
    },
});
