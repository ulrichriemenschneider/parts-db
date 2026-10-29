import { defineConfig } from 'vite';
export default defineConfig({server:{proxy:{'/api':{target:process.env.PARTSDB_API_TARGET||'http://127.0.0.1:5000'}}}});
