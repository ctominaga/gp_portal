import "@testing-library/jest-dom/vitest";

// jsdom não implementa Element.scrollIntoView nem hasPointerCapture —
// Radix Select chama os dois ao abrir o dropdown. Polyfill no-op aqui
// libera testes de Select sem afetar produção (que usa o DOM real).
if (typeof Element !== "undefined") {
  const proto = Element.prototype as unknown as Record<string, unknown>;
  if (!proto.scrollIntoView) proto.scrollIntoView = () => {};
  if (!proto.hasPointerCapture) proto.hasPointerCapture = () => false;
  if (!proto.releasePointerCapture) proto.releasePointerCapture = () => {};
}
