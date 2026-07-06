# Agent 지침

## React: useState 객체 압축

사용자가 **「useState 객체로 압축해줘」**라고 하면, 해당 컴포넌트에서 **한 화면·한 흐름에 묶인 여러 `useState`를 하나의 객체 state**로 합친다.

- `type XxxState = { ... }` 정의 후 `useState<XxxState>(초기값)` 하나만 사용
- 갱신: `setState((s) => ({ ...s, field: value }))`
- JSX는 `const { a, b } = state`로 구조 분해해 가독성 유지
- `pageSize` 등 상수·다른 도메인 상태는 분리
- **동작은 바꾸지 않고** 리팩터만 한다. 요청한 파일만 수정

참고: 폼은 `FormData` → `Object.fromEntries`처럼 관련 값을 한 객체로 다루는 패턴과 같다.
