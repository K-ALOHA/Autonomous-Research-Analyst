/// <reference types="node" />

/**
 * `process.env` keys used by API routes (Vercel: Project → Environment Variables).
 * Base `process` / `NodeJS.ProcessEnv` come from `@types/node` (see tsconfig `types`).
 */
declare namespace NodeJS {
  interface ProcessEnv {
    readonly NEXT_PUBLIC_BACKEND_URL?: string;
    readonly NEXT_PUBLIC_BACKEND_STREAM_PATH?: string;
  }
}
