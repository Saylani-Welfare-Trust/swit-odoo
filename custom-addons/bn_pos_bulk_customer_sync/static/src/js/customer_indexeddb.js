/** @odoo-module **/

// Minimal IndexedDB wrapper dedicated to the bulk customer cache.
// Deliberately NOT using the array-based in-memory model stock POS uses for
// res.partner - at 500K rows that array (and any .filter()/.find() over it)
// is exactly what makes the till unresponsive. Everything here is done
// through IndexedDB's own indexes so a lookup stays fast at any scale.

const DB_NAME = "pos_bulk_customers";
const DB_VERSION = 1;
const STORE = "customers";

function openDb() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains(STORE)) {
                const store = db.createObjectStore(STORE, { keyPath: "id" });
                store.createIndex("phone", "phone", { unique: false });
                store.createIndex("mobile", "mobile", { unique: false });
                store.createIndex("barcode", "barcode", { unique: false });
                store.createIndex("name", "name", { unique: false });
            }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

export const CustomerCache = {
    async putMany(records) {
        if (!records.length) return;
        const db = await openDb();
        await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, "readwrite");
            const store = tx.objectStore(STORE);
            for (const rec of records) store.put(rec);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
        });
    },

    async deleteMany(ids) {
        if (!ids.length) return;
        const db = await openDb();
        await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, "readwrite");
            const store = tx.objectStore(STORE);
            for (const id of ids) store.delete(id);
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
        });
    },

    // Exact index lookup - O(log n) via the browser's B-tree index, not a
    // scan. Use this first since cashiers search by phone.
    async findByPhoneExact(value) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, "readonly");
            const store = tx.objectStore(STORE);
            const results = [];
            for (const idx of ["phone", "mobile"]) {
                const req = store.index(idx).getAll(value);
                req.onsuccess = () => results.push(...req.result);
            }
            tx.oncomplete = () => resolve(dedupeById(results));
            tx.onerror = () => reject(tx.error);
        });
    },

    // Prefix search (e.g. cashier has typed the first 6 digits) using an
    // IDBKeyRange bound instead of scanning every row.
    async findByPhonePrefix(prefix, limit = 20) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, "readonly");
            const store = tx.objectStore(STORE);
            const range = IDBKeyRange.bound(prefix, prefix + "\uffff");
            const results = [];
            for (const idx of ["phone", "mobile"]) {
                if (results.length >= limit) break;
                const cursorReq = store.index(idx).openCursor(range);
                cursorReq.onsuccess = (ev) => {
                    const cursor = ev.target.result;
                    if (cursor && results.length < limit) {
                        results.push(cursor.value);
                        cursor.continue();
                    }
                };
            }
            tx.oncomplete = () => resolve(dedupeById(results));
            tx.onerror = () => reject(tx.error);
        });
    },

    async getMeta(key) {
        const db = await openDb();
        return new Promise((resolve) => {
            const tx = db.transaction(STORE, "readonly");
            // Meta values (e.g. last sync timestamp) are stashed under a
            // reserved negative id so they share the same store/tx cheaply.
            const req = tx.objectStore(STORE).get(`__meta_${key}`);
            req.onsuccess = () => resolve(req.result ? req.result.value : null);
            req.onerror = () => resolve(null);
        });
    },

    async setMeta(key, value) {
        const db = await openDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(STORE, "readwrite");
            tx.objectStore(STORE).put({ id: `__meta_${key}`, value });
            tx.oncomplete = resolve;
            tx.onerror = () => reject(tx.error);
        });
    },
};

function dedupeById(records) {
    const seen = new Map();
    for (const r of records) if (r && !`${r.id}`.startsWith("__meta_")) seen.set(r.id, r);
    return [...seen.values()];
}
