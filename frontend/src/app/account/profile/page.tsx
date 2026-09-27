import type { Metadata } from "next";

import { AccountShell, SignInRequired } from "@/components/account/AccountShell";

export const metadata: Metadata = {
  title: "Profile",
  robots: { index: false, follow: false },
};

export default function ProfilePage() {
  return (
    <AccountShell
      title="Profile"
      description="Your name, email, phone and business details used on invoices."
    >
      <SignInRequired what="your profile" />
    </AccountShell>
  );
}
