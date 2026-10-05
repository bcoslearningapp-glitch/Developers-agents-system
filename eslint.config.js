import eslint from '@eslint/js';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import tseslint from '@typescript-eslint/eslint-plugin';
import parser from '@typescript-eslint/parser';

export default [
  {
    ignores: ['dist', 'coverage', '.ts-build'],
  },
  eslint.configs.recommended,
  {
    files: [
      'src/**/*.ts',
      'src/**/*.tsx',
      'src/**/*.js',
      'vite.config.ts',
      'eslint.config.js',
    ],
    languageOptions: {
      parser: parser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.recommended.rules,
      ...tseslint.configs.recommended.rules,
      'no-console': 'error',
      'no-debugger': 'error',
    },
    // No need for react version detection without react plugin
  },
];