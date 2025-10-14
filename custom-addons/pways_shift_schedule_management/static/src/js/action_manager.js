// /** @odoo-module */

// import { registry } from "@web/core/registry";
// import { download } from "@web/core/network/download";
// import framework from 'web.framework';
// import session from 'web.session';

// registry.category("ir.actions.report handlers").add("xlsx", async (action) => {
//     if (action && action.report_type == 'xlsx') {
//         framework.blockUI();
//         var def = $.Deferred();
//         session.get_file({
//             url: '/xlsx_reports',
//             data: action.data,
//             success: def.resolve.bind(def),
//             /*error: (error) => this.call('crash_manager', 'rpc_error', error),*/
//             complete: framework.unblockUI,
//         });
//         return def;
//     }
// });

/** @odoo-module */

import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";
import { useService } from '@web/core/utils/hooks';

registry.category("ir.actions.report.handlers").add("xlsx", async (action) => {
    if (action && action.report_type === 'xlsx') {
        // Get the notification service
        const notificationService = useService('notification');

        // Show a loading notification
        notificationService.notify({
            type: 'info', 
            title: 'Downloading the report...',
            message: 'Please wait while the report is being generated.',
            sticky: true,
        });

        const def = $.Deferred();

        const downloadService = useService('download');

        downloadService.get_file({
            url: '/xlsx_reports',
            data: action.data,
            success: def.resolve.bind(def),
            complete: () => {
                // Once complete, remove the loading notification
                notificationService.removeAll();
            },
        });

        return def;
    }
});
