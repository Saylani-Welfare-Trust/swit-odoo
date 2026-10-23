/* @odoo-module */

import { Chatter } from "@mail/core/web/chatter";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { WarningDialog, ErrorDialog } from "@web/core/errors/error_dialogs"; 


// Save original methods first
Chatter.prototype._originalSetup = Chatter.prototype.setup;
Chatter.prototype._originalOnUploaded = Chatter.prototype.onUploaded;

// Patch Chatter
patch(Chatter.prototype, {
    async setup() {
        // call original setup
        this._originalSetup?.();

        // get dialog service
        this.dialog = useService("dialog");

        // getting current company max file size
        this.company = useService("company");
        const currentCompany = this.company.currentCompany;
        const companyId = currentCompany.id;
        const companyData = await this.orm.call('res.company', 'read', [[companyId], ['max_file_size']]);
        this.maxFileSize_mb = companyData[0].max_file_size || 0;
        this.maxFileSize = this.maxFileSize_mb * 1024 * 1024;
    },

    async onUploaded(file) {
        console.warn("Uploaded File size (bytes)", file.size);

        if (this.maxFileSize && file.size > this.maxFileSize) {
            this.dialog.add(WarningDialog, {
                title: "Warning",
                message: `File exceeds the maximum allowed size of ${this.maxFileSize_mb} MB.`,
            });
            return false;
        }
        return this._originalOnUploaded?.(file);
    },
});
