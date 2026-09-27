import type { Metadata } from "next";

import { AccountShell, SignInRequired } from "@/components/account/AccountShell";

export const metadata: Metadata = {
  title: "Saved addresses",
  robots: { index: false, follow: false },
};

export default function AddressesPage() {
  return (
    <AccountShell
      title="Saved addresses"
      description="Delivery and billing addresses, including GST details for business invoices."
    >
      <SignInRequired what="your saved addresses" />
    </AccountShell>
  );
}
