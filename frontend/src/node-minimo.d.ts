// Declaraciones mínimas de Node solo para `versiones.spec.ts`, que lee ficheros del
// repositorio. Evita añadir `@types/node` (Constitución VIII: dependencias mínimas).
declare module 'node:fs' {
  export function readFileSync(ruta: string): Uint8Array;
  export function readFileSync(ruta: string, codificacion: 'utf8'): string;
}
declare module 'node:crypto' {
  export function createHash(algoritmo: 'sha256'): {
    update(datos: Uint8Array): { digest(formato: 'hex'): string };
  };
}
declare const process: { cwd(): string };
