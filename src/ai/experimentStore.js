const ExperimentStore = (() => {
    const KEY = "self-driving-car-experiment";
    const DB_NAME = "self-driving-car";
    const DB_VERSION = 1;
    const STORE = "experiments";
    const RECORD = "latest";

    let idb = null;

    function supportsIdb() {
        return typeof indexedDB !== "undefined";
    }

    function openDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE)) {
                    db.createObjectStore(STORE);
                }
            };
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => reject(req.error);
        });
    }

    async function idbSave(payload) {
        if (!idb) idb = await openDB();
        return new Promise((resolve, reject) => {
            const tx = idb.transaction(STORE, "readwrite");
            tx.objectStore(STORE).put(payload, RECORD);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async function idbLoad() {
        if (!idb) idb = await openDB();
        return new Promise((resolve, reject) => {
            const tx = idb.transaction(STORE, "readonly");
            const req = tx.objectStore(STORE).get(RECORD);
            req.onsuccess = () => resolve(req.result || null);
            req.onerror = () => reject(req.error);
        });
    }

    async function idbClear() {
        if (!idb) idb = await openDB();
        return new Promise((resolve, reject) => {
            const tx = idb.transaction(STORE, "readwrite");
            tx.objectStore(STORE).delete(RECORD);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    function lsSave(payload) {
        localStorage.setItem(KEY, JSON.stringify(payload));
    }

    function lsLoad() {
        try {
            return JSON.parse(localStorage.getItem(KEY)) || null;
        } catch (e) {
            return null;
        }
    }

    function lsClear() {
        localStorage.removeItem(KEY);
    }

    return {
        save(payload) {
            if (supportsIdb()) return idbSave(payload);
            lsSave(payload);
            return Promise.resolve();
        },
        load() {
            if (supportsIdb()) return idbLoad();
            return Promise.resolve(lsLoad());
        },
        clear() {
            if (supportsIdb()) return idbClear();
            lsClear();
            return Promise.resolve();
        },
        exists() {
            if (supportsIdb()) return idbLoad().then(d => !!d);
            return Promise.resolve(!!localStorage.getItem(KEY));
        }
    };
})();