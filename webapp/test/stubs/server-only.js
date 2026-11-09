// `server-only` throws when imported outside a React Server Component
// bundle, which is exactly what a Node test is. Vitest aliases the package
// here (vitest.config.mts) so server modules can be unit-tested.
export {};
