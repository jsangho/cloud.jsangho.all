import { Suspense } from "react";
import { OAuthCallbackHandler } from "./oauth-callback-handler";

export const dynamic = "force-dynamic";

export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={null}>
      <OAuthCallbackHandler />
    </Suspense>
  );
}
