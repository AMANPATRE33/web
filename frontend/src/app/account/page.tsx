import type { Metadata } from "next";

import { AccountShell, SignInRequired } from "@/components/account/AccountShell";

export const metadata: Metadata = {
  title: "Your account",
  robots: { index: false, follow: false },
};

export default function AccountPage() {
  return (
    <AccountShell
      title="Your account"
      description="Orders, saved addresses, your wishlist and your profile details in one place."
    >
      <SignInRequired what="your account" />
    </AccountShell>
  );
}
