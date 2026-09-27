import type { Metadata } from "next";

import { AccountShell, SignInRequired } from "@/components/account/AccountShell";

export const metadata: Metadata = {
  title: "Order history",
  robots: { index: false, follow: false },
};

export default function OrdersPage() {
  return (
    <AccountShell
      title="Orders"
      description="Every order you have placed, with its status, tracking and invoice."
    >
      <SignInRequired what="your order history" />
    </AccountShell>
  );
}
