const DB_NAME = 'spotme'
const DB_VERSION = 1

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains('offline_sets')) db.createObjectStore('offline_sets', { keyPath: 'id', autoIncrement: true })
      if (!db.objectStoreNames.contains('cached_layout')) db.createObjectStore('cached_layout', { keyPath: 'screen' })
      if (!db.objectStoreNames.contains('cached_workout')) db.createObjectStore('cached_workout', { keyPath: 'id' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export const offlineDB = {
  async saveSet(set: object) {
    const db = await openDB()
    const tx = db.transaction('offline_sets', 'readwrite')
    tx.objectStore('offline_sets').add({ ...set, timestamp: Date.now() })
    return new Promise<void>((res) => { tx.oncomplete = () => res() })
  },
  async getOfflineSets(): Promise<object[]> {
    const db = await openDB()
    const tx = db.transaction('offline_sets', 'readonly')
    return new Promise((resolve) => { const req = tx.objectStore('offline_sets').getAll(); req.onsuccess = () => resolve(req.result) })
  },
  async clearOfflineSets() {
    const db = await openDB()
    const tx = db.transaction('offline_sets', 'readwrite')
    tx.objectStore('offline_sets').clear()
  },
  async cacheLayout(layout: object & { screen: string }) {
    const db = await openDB()
    const tx = db.transaction('cached_layout', 'readwrite')
    tx.objectStore('cached_layout').put(layout)
  },
  async getCachedLayout(screen: string): Promise<object | undefined> {
    const db = await openDB()
    const tx = db.transaction('cached_layout', 'readonly')
    return new Promise((resolve) => { const req = tx.objectStore('cached_layout').get(screen); req.onsuccess = () => resolve(req.result) })
  },
}
