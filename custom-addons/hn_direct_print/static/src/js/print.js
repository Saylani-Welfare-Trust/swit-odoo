/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { session } from "@web/session";
import { makeContext } from "@web/core/context";

const originalExecuteAction = ActionMenus.prototype.executeAction;

patch(ActionMenus.prototype, {
    patchName: "hn_direct_print.patch_executeAction",

    async fetchPdfBase64(reportName, activeIds, context = {}) {
        // Fetch the base64 PDF from the server

        const res = await this.orm.rpc('/hn_direct_print/base64_report', {
            report_name: reportName,
            docids: activeIds,
            context: context,
        });
        if (res.success) {
            return {"pdf": res.pdf, "name": res.name};
        } else {
            throw new Error(res.error || 'Failed to generate report');
        }
    },


    async base64ToBlob(base64, mime = "application/pdf") {
        // Convert base64 string to Blob

        if (base64.startsWith("data:")) {
            base64 = base64.split(",")[1];
        }
        base64 = base64.replace(/\s/g, "");
        const pad = base64.length % 4;
        if (pad) {
            base64 += "=".repeat(4 - pad);
        }

        const byteChars = window.atob(base64);
        const byteNumbers = new Uint8Array(byteChars.length);

        for (let i = 0; i < byteChars.length; i++) {
            byteNumbers[i] = byteChars.charCodeAt(i);
        }

        return new Blob([byteNumbers], { type: mime });
    },


    async executeAction(action) {

        let activeIds = this.props.getActiveIds();
        if (this.props.isDomainSelected) {
            activeIds = await this.orm.search(this.props.resModel, this.props.domain, {
                limit: session.active_ids_limit,
                context: this.props.context,
            });
        }
        const activeIdsContext = {
            active_id: activeIds[0],
            active_ids: activeIds,
            active_model: this.props.resModel,
        };
        if (this.props.domain) {
            // keep active_domain in context for backward compatibility
            // reasons, and to allow actions to bypass the active_ids_limit
            activeIdsContext.active_domain = this.props.domain;
        }
        const context = makeContext([this.props.context, activeIdsContext]);

        try {
            const orm = this.orm;
            const user = await orm.read("res.users", [session.uid], ["enabled_direct_print", "printer_name"]);
            if (user[0].enabled_direct_print) {
                console.log("hn_direct_print: Direct print enabled for user, attempting direct print");
                
                // Fetch full report action from ir.actions.report
                const reportActions = await orm.read("ir.actions.report", [action.id], [
                    "report_name",
                    "report_type",
                ]);
                const reportAction =  reportActions[0];

                // if report is PDF, try to send to local printing API
                if (reportAction.report_type === "qweb-pdf") {

                    // Fetch current user's printer_name
                    const printerName = user[0].printer_name;

                    if (!printerName) {
                        console.warn("No printer configured for current user");
                    }

                    // Fetch the PDF report as base64
                    const {pdf, name} = await this.fetchPdfBase64(reportAction.report_name, activeIds, context);

                    // Convert base64 to Blob
                    const blob = await this.base64ToBlob(pdf, "application/pdf");

                    // Send to local printing API
                    const apiData = new FormData(); 
                    apiData.append("printer_name", printerName || null);
                    apiData.append("file", blob, name || "report.pdf");

                    const apiResp = await fetch("http://localhost:5000/print/pdf", {
                        method: "POST",
                        body: apiData,
                    });
                    
                    if (apiResp.ok) {
                        console.log("hn_direct_print: PDF sent to API successfully, skipping default download");
                        return { success: true };
                    }
                    console.warn("API call failed, falling back to default executeAction", apiResp);
                };
            };

        } catch (err) {
            console.error("hn_direct_print: Error in custom executeAction, fallback", err);
        }

        // Fallback to original behavior
        return this.actionService.doAction(action.id, {
            additionalContext: context,
            onClose: this.props.onActionExecuted,
        });

    },
});
