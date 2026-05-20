import Link from "next/link";
import { Lock } from "lucide-react";

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary-50 to-neutral-100 px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-600 shadow-lg">
            <span className="text-2xl font-bold text-white">F</span>
          </div>
          <h1 className="text-2xl font-bold text-neutral-900">Sign-up disabled</h1>
          <p className="mt-1 text-sm text-neutral-500">
            This is the public FieldPro demo.
          </p>
        </div>

        <div className="card p-7">
          <div className="mb-5 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <p className="text-sm text-amber-900">
              Account creation is turned off so the demo data stays predictable.
              Use the quick-login buttons on the login page instead.
            </p>
          </div>

          <Link href="/login" className="btn-primary block w-full py-2.5 text-center">
            Go to demo login
          </Link>
        </div>

        <p className="mt-6 text-center text-sm text-neutral-500">
          Want your own instance? View the source on{" "}
          <a
            href="https://github.com/one-repo-to-rule-them-all/poc_fieldpro"
            target="_blank"
            rel="noreferrer noopener"
            className="font-medium text-primary-600 hover:text-primary-700"
          >
            GitHub
          </a>
          .
        </p>
      </div>
    </div>
  );
}
