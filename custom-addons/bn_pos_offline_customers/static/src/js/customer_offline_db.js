/** @odoo-module **/

// Lightweight IndexedDB wrapper for offline customer search.
// Stores only id / name / phone / mobile per customer, plus lowercase
// copies of name and phone used purely for fast prefix search via
// IndexedDB indexes (avoids scanning every record on each keystroke).

const DB_NAME = "pos_offline_customers_db";
const STORE_NAME = "customers";
const DB_VERSION = 1;

const LAST_SYNC_KEY = "pos_customers_last_sync";

let dbPromise = null;

function openCustomerDB() {
    if (dbPromise) {
        return dbPromise;
    }
    dbPromise = new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
                store.createIndex("name_lower", "name_lower", { unique: false });
                store.createIndex("phone_lower", "phone_lower", { unique: false });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
    return dbPromise;
}

/**
 * Insert or update a batch of lightweight customer records.
 * @param {Array<{id:number, name:string, phone:string, mobile:string}>} records
 */
export async function putCustomers(records) {
    if (!records || !records.length) {
        return;
    }
    const db = await openCustomerDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readwrite");
        const store = tx.objectStore(STORE_NAME);
        for (const rec of records) {
            store.put({
                id: rec.id,
                name: rec.name || "",
                phone: rec.phone || "",
                mobile: rec.mobile || "",
                name_lower: (rec.name || "").toLowerCase(),
                phone_lower: ((rec.phone || rec.mobile || "") + "").toLowerCase(),
            });
        }
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

function prefixRange(prefix) {
    // Matches any indexed value starting with `prefix`.
    return IDBKeyRange.bound(prefix, prefix + "\uffff", false, false);
}

function collectFromIndex(store, indexName, query, limitResults, seen) {
    return new Promise((resolve, reject) => {
        const index = store.index(indexName);
        const request = index.openCursor(prefixRange(query));
        request.onsuccess = (event) => {
            const cursor = event.target.result;
            if (!cursor || seen.size >= limitResults) {
                resolve();
                return;
            }
            seen.set(cursor.value.id, cursor.value);
            cursor.continue();
        };
        request.onerror = () => reject(request.error);
    });
}

/**
 * Search cached customers by name or phone prefix. Works fully offline.
 * @param {string} query raw text typed by the cashier
 * @param {number} limitResults max number of results to return
 * @returns {Array<{id:number, name:string, phone:string, mobile:string}>}
 */
export async function searchCustomersLocal(query, limitResults = 20) {
    const q = (query || "").trim().toLowerCase();
    if (!q) {
        return [];
    }
    const db = await openCustomerDB();
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const seen = new Map();

    await collectFromIndex(store, "name_lower", q, limitResults, seen);
    if (seen.size < limitResults) {
        await collectFromIndex(store, "phone_lower", q, limitResults, seen);
    }

    return Array.from(seen.values()).map((rec) => ({
        id: rec.id,
        name: rec.name,
        phone: rec.phone,
        mobile: rec.mobile,
    }));
}

export async function getCachedCustomerCount() {
    const db = await openCustomerDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, "readonly");
        const req = tx.objectStore(STORE_NAME).count();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

export function getLastSync() {
    return localStorage.getItem(LAST_SYNC_KEY) || false;
}

export function setLastSync(value) {
    localStorage.setItem(LAST_SYNC_KEY, value);
}

export { LAST_SYNC_KEY };
