# SpotMe Frontend

React 19 + TypeScript + Vite PWA. Renders dynamic layouts from Claude's JSON descriptors.

## Key Pattern: Layout-Driven UI

The frontend does NOT define fixed screens. Claude generates JSON layout descriptors,
and `layout-renderer.tsx` maps component types to React components. Adding a new
component type requires:

1. create `components/new-component.tsx`
2. add it to `COMPONENT_MAP` in `layout-renderer.tsx`
3. add the type to `VALID_COMPONENT_TYPES` in `server/services/layout_service.py`
4. add the type to the `ComponentType` union in `types.ts`

## Offline-First

- IndexedDB caches layouts and queues sets logged while offline
- `use-offline` hook syncs pending data on reconnect
- dashboard and workout screens fall back to cached layouts when server unreachable
- all set logging works without network — syncs later

## Conventions

- one component per file, file name matches component (kebab-case)
- hooks prefixed with `use-` (kebab-case files, camelCase exports)
- all API calls go through `api.ts` — never use raw `fetch` in components
- use `import type` for type-only imports (Vite 8 `verbatimModuleSyntax`)
- screens are in `screens/`, reusable components in `components/`

## API Proxy

Dev server proxies `/api` to `http://localhost:8000` (configured in `vite.config.ts`).
In production, the built PWA is served by the same FastAPI server.
