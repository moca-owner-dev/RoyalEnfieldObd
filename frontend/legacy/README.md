# Legacy / backup del tablero original

Snapshot del diseño v0.1 del frontend, antes del redesign mobile-landscape.

Para restaurar la versión original:

```bash
cp legacy/App.vue.original src/App.vue
cp legacy/style.css.original src/style.css
cp -r legacy/components.original/* src/components/
```

También disponible vía git tag: `git checkout v0.1-original-layout`
