import { defineConfig } from "vitest/config";
import { transform } from "esbuild";

// Next projects keep JSX in .js files; teach Vite to treat app/*.js as JSX before it analyses imports.
const jsAsJsx = {
  name: "js-as-jsx",
  enforce: "pre",
  async transform(code, id) {
    if (!/[\\/]app[\\/].*\.js$/.test(id)) return null;
    const out = await transform(code, { loader: "jsx", jsx: "automatic", sourcemap: true, sourcefile: id });
    return { code: out.code, map: out.map };
  },
};
export default defineConfig({
  plugins: [jsAsJsx],
  test: { environment: "jsdom", include: ["tests/**/*.test.jsx"], globals: true },
});
