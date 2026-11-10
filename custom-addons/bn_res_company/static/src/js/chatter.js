/* @odoo-module */

import { Chatter } from "@mail/core/web/chatter";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { WarningDialog } from "@web/core/errors/error_dialogs";

// Refuse a chatter upload larger than the company's Max File Size (MB) before
// it is sent; the server checks it again (ir.attachment).
patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
        this.companyService = useService("company");
        this.maxFileSizeMb = 0;
        const companyId = this.companyService.currentCompany.id;
        this.orm.read("res.company", [companyId], ["max_file_size"]).then((data) => {
            this.maxFileSizeMb = (data[0] && data[0].max_file_size) || 0;
        });
    },

    async onUploaded(file) {
        const maxBytes = this.maxFileSizeMb * 1024 * 1024;
        if (maxBytes && file.size > maxBytes) {
            this.dialog.add(WarningDialog, {
                title: "Warning",
                message: `File exceeds the maximum allowed size of ${this.maxFileSizeMb} MB.`,
            });
            return false;
        }
        return super.onUploaded(...arguments);
    },
});
