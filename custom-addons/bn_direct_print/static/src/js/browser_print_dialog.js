/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

function _getHtmlReportUrl(action) {
    let url = `/report/html/${action.report_name}`;
    const actionContext = action.context || {};
    
    if (action.data && JSON.stringify(action.data) !== "{}") {
        const options = encodeURIComponent(JSON.stringify(action.data));
        const context = encodeURIComponent(JSON.stringify(actionContext));
        url += `?options=${options}&context=${context}`;
    } else {
        if (actionContext.active_ids) {
            url += `/${actionContext.active_ids.join(",")}`;
        }
        const context = encodeURIComponent(JSON.stringify(actionContext));
        url += `?context=${context}`;
    }
    return url;
}

async function printHtmlReport(action, env) {
    try {
        const url = _getHtmlReportUrl(action);
        const response = await fetch(url);
        if (!response.ok) throw new Error(response.statusText);
        
        const content = await response.text();
        const printWindow = window.open('', '_blank');
        
        if (printWindow) {
            // Clone styles
            Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
                .forEach(node => printWindow.document.head.appendChild(node.cloneNode(true)));
            
            // Write content
            printWindow.document.write(content);
            printWindow.document.close();
            
            // Hide control panel elements
            printWindow.document.querySelectorAll('.o_control_panel_main_buttons')
                .forEach(btn => btn.style.display = 'none');
            
            // Trigger print
            printWindow.onload = () => {
                printWindow.print();
                setTimeout(() => printWindow.close(), 500);
            };
            return true;
        } else {
            env.services.notification.add(_t("Allow pop-ups to print"), {
                type: "danger",
                sticky: true
            });
            return false;
        }
    } catch (error) {
        env.services.notification.add(_t("HTML print failed: ") + error.message, {
            type: "danger",
            sticky: true
        });
        return false;
    }
}

registry.category("ir.actions.report handlers").add("html_print_handler", async (action, options, env) => {
    // console.log(action);

    // Only handle HTML reports
    if (action.report_type === "qweb-pdf" || action.report_type === "qweb-html") {
        return printHtmlReport(action, env);
    }
    return false;
});