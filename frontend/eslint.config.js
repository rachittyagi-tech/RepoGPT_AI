// eslint.config.js — ESLint 9 flat config (Step 14).
//
// This file did not exist before Step 14: package.json's `lint` script
// (`eslint . --ext ts,tsx ...`) would fail immediately with "no
// configuration found", since ESLint 9 requires a flat config by default
// and no `.eslintrc*` was ever present either.
//
// Built ONLY from packages already in package.json
// (@typescript-eslint/parser + @typescript-eslint/eslint-plugin) rather
// than adding the `typescript-eslint` meta-package or `@eslint/js` as new
// dependencies — keeps this a config-only fix, not a dependency change.

import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

export default [
  {
    ignores: ["dist/**", "node_modules/**", "coverage/**"],
  },
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
      },
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        fetch: "readonly",
        localStorage: "readonly",
        sessionStorage: "readonly",
        navigator: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        setInterval: "readonly",
        clearInterval: "readonly",
        URL: "readonly",
        Blob: "readonly",
        FormData: "readonly",
      },
    },
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "no-console": ["warn", { allow: ["warn", "error"] }],
    },
  },
];
