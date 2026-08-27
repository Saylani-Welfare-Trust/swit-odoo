/** @odoo-module **/
/* ERP Heritage - Dashboard Builder
 * RFC 4180 CSV cell escaping + spreadsheet formula-injection guard. A label
 * like "Acme, Inc." must not shift columns, and "=cmd|..." must not execute
 * when the file is opened in Excel / Sheets. */

export function csvCell(v) {
    let s = v === null || v === undefined ? "" : String(v);
    // Neutralise a leading formula trigger (= + - @, tab, CR) before any quoting.
    if (/^[=+\-@\t\r]/.test(s)) {
        s = "'" + s;
    }
    // Quote if the value contains a comma, quote, or newline; double inner quotes.
    if (/[",\n\r]/.test(s)) {
        s = '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
}

export function csvRow(cells) {
    return cells.map(csvCell).join(",");
}
