import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AccountShell, SignInRequired } from "@/components/account/AccountShell";

export const metadata: Metadata = {
  title: "Order details",
  robots: { index: false, follow: false },
};

export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // Without an order API and without a session there is no order to look up.
  // 404 is the honest response: a link to a non-existent order is a dead end,
  // and rendering a fabricated order would be worse.
  if (!id || id.length < 8) notFound();

  return (
    <AccountShell title="Order" description={`Order ${id}`}>
      <SignInRequired what="this order" />
    </AccountShell>
  );
}
