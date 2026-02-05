import { memo } from 'react'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

function CtaBanner() {
  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="relative overflow-hidden rounded-3xl bg-cta-gradient p-10 sm:p-14">
        {/* Ambient glow */}
        <div
          className="absolute left-1/2 top-0 -translate-x-1/2 h-40 w-80 rounded-full bg-mint-500/15 blur-3xl"
          aria-hidden="true"
        />

        <div className="relative text-center">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Ready to decode your next filing?
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-lg text-slate-300">
            Stop spending hours on filings. Get the insights that matter in minutes.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex items-center gap-2 rounded-full bg-mint-500 px-8 py-3.5 text-base font-semibold text-white shadow-glow-mint transition-all hover:bg-mint-400 hover:shadow-glow-mint-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
            >
              Get Started Free
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/company/AAPL"
              className="inline-flex items-center gap-2 rounded-full border border-white/20 px-8 py-3.5 text-base font-semibold text-white transition-all hover:border-white/40 hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              See an Example
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}

export default memo(CtaBanner)
