import nextConfig from "eslint-config-next/core-web-vitals";
import tsPlugin from "@typescript-eslint/eslint-plugin";

export default [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      /* 다른 저장소에서 옮겨 온 코드 — Super-Sub 목업 (2026-10-06).
         `.prettierignore` 와 같은 이유로 뺀다: 원본의 규칙이 여기와 달라
         (console 허용 · 미사용 변수 허용) 가져온 그대로는 이 설정을 통과하지
         못한다. 🔴 **고쳐서 통과시키지 않는다** — 고치면 원본과 갈라져
         `supersub/port-from-team.sh` 로 다시 옮길 때마다 같은 손질을 반복해야
         하고, 그 손질이 남의 코드에 대한 것이라 되돌려 보낼 수도 없다.
         이 저장소가 직접 쓴 코드는 그대로 검사한다. */
      "supersub/**",
      "app/(supersub)/**",
      "app/api/supersub/**",
    ],
  },
  ...nextConfig,
  {
    plugins: {
      "@typescript-eslint": tsPlugin,
    },
    rules: {
      "no-console": "error",
      "react-hooks/set-state-in-effect": "off",
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },
];
